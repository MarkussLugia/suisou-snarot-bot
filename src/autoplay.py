"""
自动玩家相关的类：
``中间件路由 -> 消息处理 -> 决策 -> 行动 -> 中间件操作``

在消息处理中插入 AutoPlayerDispatcher 作为双向中间件，
按需挂载 AutoPlayer。
"""

import asyncio
import random
from dataclasses import dataclass
from typing import Literal

from game import (
    FieldColor,
    FieldSnapshot,
    SnarotBotHooks,
    SnarotCard,
    SnarotGame,
    TurnSnapshot,
)
from shared import format_exception

COLORS: tuple[FieldColor, ...] = ("r", "g", "b", "y")
DrawReason = Literal["deal", "pass", "collapse", "attack", "self_draw"]


# 行为类
@dataclass(frozen=True)
class Play:
    card_index: int
    color: FieldColor | None = None


@dataclass(frozen=True)
class Pass:
    pass


PlayerAction = Play | Pass


# 策略类
class PlayerStrategy:
    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng if rng is not None else random.Random()

    def decide(self, turn: TurnSnapshot) -> tuple[PlayerAction, str]:
        raise NotImplementedError


class RandomStrategy(PlayerStrategy):
    """
    随机策略。
    受到抽卡预言攻击时，按照概率优先随机打出清除牌。
    其余情况下卡牌随机打出。
    """

    clear_pref: float

    def __init__(
        self,
        rng: random.Random | None = None,
        *,
        clear_pref: float = 0.8,
    ) -> None:
        super().__init__(rng)
        self.clear_pref = clear_pref

    def decide(self, turn: TurnSnapshot) -> tuple[PlayerAction, str]:
        if not turn.usable:
            return (Pass(), "没有可打出的牌。")

        note = ""
        index = self.rng.choice(turn.usable)

        under_attack = turn.draw_hold > 0
        wants_clear = self.rng.random() < self.clear_pref
        clear_cards = [index for index in turn.usable if turn.hand[index].clearAttack]

        if under_attack:
            note += f"有抽卡预言（{turn.draw_hold}张，{turn.draw_delay}回合）。"
            if wants_clear:
                note += "想要清除。"
                if clear_cards:
                    note += "打出清除牌。"
                    index = self.rng.choice(clear_cards)
                else:
                    note += "没有清除牌。"
            else:
                note += "暂时不想清除。"

        card = turn.hand[index]
        color = self.rng.choice(COLORS) if card.updateColor == "s" else None
        note += f"打出了[{card.name}]。"
        return (Play(index, color), note)


# 自动玩家类
class AutoPlayerHooks:
    """
    自动玩家的 Hooks 类。
    """

    def on_message(self, player_id: str, message: str) -> None:
        """自动玩家发出调试消息。"""

    def on_command(self, player_id: str, command: PlayerAction) -> None:
        """自动玩家发出指令。"""

    def on_error(self, player_id: str, detail: str) -> None:
        """自动玩家报告错误。"""


class AutoPlayer:
    """
    自动玩家的 wrapper 类。
    处理收到的回合，并通过 Hooks 返回操作。
    """

    def __init__(
        self,
        player_id: str,
        strategy: PlayerStrategy,
        hooks: AutoPlayerHooks | None = None,
        think_time: float = 1.0,
    ) -> None:
        self.player_id = player_id
        self.strategy = strategy
        self.think_time = think_time
        self.task: asyncio.Task | None = None

        self.hooks = hooks if hooks is not None else AutoPlayerHooks()
        self.last_turn_count: int = -1

    def register(self, hooks: AutoPlayerHooks):
        self.cancel()
        self.hooks = hooks
        self.last_turn_count: int = -1

    def cancel(self) -> None:
        if self.task is not None:
            self.task.cancel()

    def notify_turn(self, turn: TurnSnapshot, turn_count: int) -> None:
        """
        收到自己回合开始的提醒时调用。
        开始处理此回合。
        """
        if turn_count <= self.last_turn_count:
            return
        self.last_turn_count = turn_count
        self.cancel()
        task = asyncio.create_task(self.__run(turn, turn_count))
        self.task = task
        task.add_done_callback(self.__run_done)

    def __run_done(self, task: asyncio.Task) -> None:
        err_str = format_exception(task)
        if err_str:
            self.hooks.on_error(self.player_id, err_str)

    async def __run(self, turn: TurnSnapshot, turn_count: int) -> None:
        if self.think_time > 0:
            await asyncio.sleep(self.think_time)
        if turn_count < self.last_turn_count:
            return
        (action, reason) = self.strategy.decide(turn)
        if reason:
            self.hooks.on_message(self.player_id, reason)
        self.hooks.on_command(self.player_id, action)


# 自动玩家转发路由
class AutoPlayerDispatcher(SnarotBotHooks, AutoPlayerHooks):
    """
    自动玩家的事件转发中间件。
    将事件透传给 game_hook_sink，
    同时将属于自动玩家的回合开始事件转发给自动玩家。
    """

    def __init__(
        self,
        game: SnarotGame,
        game_hook_sink: SnarotBotHooks | None = None,
        ap_hook_sink: AutoPlayerHooks | None = None,
    ) -> None:
        self.game = game
        self.game_hook_sink = (
            game_hook_sink if game_hook_sink is not None else SnarotBotHooks()
        )
        self.ap_hook_sink = (
            ap_hook_sink if ap_hook_sink is not None else AutoPlayerHooks()
        )
        self.auto_players: dict[str, AutoPlayer] = {}

    def register(self, auto_player: AutoPlayer) -> None:
        self.auto_players[auto_player.player_id] = auto_player
        auto_player.register(self)

    def cancel_all(self) -> None:
        for auto_player in self.auto_players.values():
            auto_player.cancel()

    def attach_game_hooks(self, game_hook_sink: SnarotBotHooks):
        self.game_hook_sink = game_hook_sink

    def attach_ap_hooks(self, ap_hook_sink: AutoPlayerHooks):
        self.ap_hook_sink = ap_hook_sink

    # game_hook_sink 的原始 hooks
    # dispatcher 本身只需要转发 on_turn_start 处理事件
    # 在游戏结束时释放自动玩家的 coroutine
    # 其余的 hooks 透传不做处理
    def on_turn_start(
        self,
        player_id: str,
        turn: TurnSnapshot,
        turn_count: int,
        turn_timeout: int,
    ) -> None:
        auto_player = self.auto_players.get(player_id)
        if auto_player is not None:
            auto_player.notify_turn(turn, turn_count)
        self.game_hook_sink.on_turn_start(player_id, turn, turn_count, turn_timeout)

    def on_player_win(self, player_id: str, rank: list[tuple[str, int]]) -> None:
        self.game_hook_sink.on_player_win(player_id, rank)
        self.cancel_all()

    def on_draw_exceeded_end(
        self, draw_count: int, rank: list[tuple[str, int]]
    ) -> None:
        self.game_hook_sink.on_draw_exceeded_end(draw_count, rank)
        self.cancel_all()

    def on_draw(
        self,
        player_id: str,
        cards: list[SnarotCard],
        type: DrawReason,
    ) -> None:
        self.game_hook_sink.on_draw(player_id, cards, type)

    def on_play(
        self, player_id: str, card: SnarotCard | None, field: FieldSnapshot
    ) -> None:
        self.game_hook_sink.on_play(player_id, card, field)

    def on_collapse(self) -> None:
        self.game_hook_sink.on_collapse()

    def on_turn_timeout(self, player_id: str) -> None:
        self.game_hook_sink.on_turn_timeout(player_id)

    def on_need_color_pick(self, player_id: str, index: int, card: SnarotCard) -> None:
        self.game_hook_sink.on_need_color_pick(player_id, index, card)

    def on_not_ready(self, player_ids: list[str]) -> None:
        self.game_hook_sink.on_not_ready(player_ids)

    def on_group_message(self, text: str) -> None:
        self.game_hook_sink.on_group_message(text)

    def on_private_message(self, player_id: str, text: str) -> None:
        self.game_hook_sink.on_private_message(player_id, text)

    # ap_hook_sink 的原始 hooks
    # 收到 on_command 事件时，向游戏发送对应指令
    # 其余的 hooks 透传不做处理
    # 下级 sink 不应再对 on_command 进行游戏操作
    def on_command(self, player_id: str, command: PlayerAction) -> None:
        self.ap_hook_sink.on_command(player_id, command)
        if isinstance(command, Pass):
            self.game.handle_pass(player_id)
        else:
            self.game.handle_play(player_id, command.card_index, command.color)

    def on_message(self, player_id: str, message: str) -> None:
        self.ap_hook_sink.on_message(player_id, message)

    def on_error(self, player_id: str, detail: str) -> None:
        self.ap_hook_sink.on_error(player_id, detail)
