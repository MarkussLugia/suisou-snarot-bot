import asyncio
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import partial
from random import randint, shuffle
from typing import Generic, Literal, TypeVar, cast

from data import SnarotJSONCardData


class SnarotCard:
    def __init__(self, data: SnarotJSONCardData):
        self.name = data.name
        self.img = data.img
        self.number = data.number
        self.applyColor = data.applyColor
        self.updateColor = data.updateColor
        self.addToTower = data.addToTower
        self.reverse = data.reverse
        self.clearAttack = data.clearAttack
        self.disable = data.disable
        self.attackDraw = data.attackDraw
        self.attackDelay = data.attackDelay
        self.selfDraw = data.selfDraw
        self.collapse = data.collapse


T = TypeVar("T")


class CardPile(Generic[T]):
    __cards: list[T]

    def __init__(self):
        self.__cards = []

    def append(self, content: T | Iterable[T]):
        if isinstance(content, Iterable):
            self.__cards.extend(content)
        else:
            self.__cards.append(content)
        shuffle(self.__cards)

    def draw(self, count: int) -> list[T]:
        if count < 0:
            raise ValueError
        result: list[T] = []
        while len(self.__cards) > 0 and len(result) < count:
            result.append(self.__cards.pop())
        return result

    def __bool__(self):
        return len(self.__cards) > 0

    def __len__(self):
        return len(self.__cards)


class NoPlayerException(Exception):
    pass


class PlayerOpException(Exception):
    pass


class SnarotPlayer:
    id: str
    deck: list[SnarotCard]
    draw_hold: int = 0
    draw_delay: int = 0
    skip: bool = False
    ready: bool = False

    @property
    def empty(self) -> bool:
        return len(self.deck) == 0

    def __init__(self, id: str):
        self.id = id
        self.deck = []

    def get_card(self, index: int) -> SnarotCard:
        if index < 0 or index >= len(self.deck):
            raise IndexError
        return self.deck[index]

    def delete_card(self, index: int) -> SnarotCard:
        if index < 0 or index >= len(self.deck):
            raise IndexError
        return self.deck.pop(index)


class SnarotGamePlayerManager:
    __players: list[SnarotPlayer]
    __player_map: dict[str, SnarotPlayer]
    __current_index: int = 0
    __is_reverse: bool = False

    def __init__(self):
        self.__players = []
        self.__player_map = {}

    @property
    def __bumped_index(self) -> int:
        if not len(self.__players):
            raise NoPlayerException()
        index = self.__current_index
        if self.__is_reverse:
            index -= 1
        else:
            index += 1
        return index % len(self.__players)

    def shuffle(self):
        shuffle(self.__players)
        self.__current_index = 0
        self.__is_reverse = False

    def add_player(self, player_id: str):
        if player_id in self.__player_map:
            raise PlayerOpException()
        player = SnarotPlayer(player_id)
        self.__players.append(player)
        self.__player_map[player_id] = player
        self.shuffle()

    def get_player(self, player_id: str) -> SnarotPlayer | None:
        return self.__player_map.get(player_id)

    def remove_player(self, player_id: str):
        if player_id not in self.__player_map:
            raise PlayerOpException()
        player = self.__player_map[player_id]
        del self.__player_map[player_id]
        self.__players.remove(player)
        self.shuffle()

    def remove_player_preserve_order(self, player_id: str):
        if player_id not in self.__player_map:
            raise PlayerOpException("错误：尝试移除局内没有的玩家")

        player = self.__player_map[player_id]
        del self.__player_map[player_id]

        index = self.__players.index(player)
        del self.__players[index]

        if index < self.__current_index:
            self.__current_index -= 1

        elif index == self.__current_index:
            # 如果移除的是当前玩家，让 index 落到下一位玩家
            if not self.__players:
                self.__current_index = 0
            elif self.__is_reverse:
                self.__current_index = (index - 1) % len(self.__players)
            else:
                self.__current_index = index % len(self.__players)

    def get_current_player(self) -> SnarotPlayer:
        if not len(self.__players):
            raise NoPlayerException()
        return self.__players[self.__current_index]

    def get_next_player(self) -> SnarotPlayer:
        if not len(self.__players):
            raise NoPlayerException()
        return self.__players[self.__bumped_index]

    def proceed(self):
        if not len(self.__players):
            raise NoPlayerException()
        self.__current_index = self.__bumped_index

    def reverse(self):
        self.__is_reverse = not self.__is_reverse

    def get_not_ready(self) -> list[str]:
        return [player.id for player in self.__players if not player.ready]

    def get_winner(self) -> SnarotPlayer | None:
        for player in self.__players:
            if player.empty:
                return player
        return None

    def get_rank(self) -> list[tuple[str, int]]:
        decks_len = [(player.id, len(player.deck)) for player in self.__players]
        return sorted(decks_len, key=lambda x: x[1])

    def __len__(self):
        return len(self.__players)

    def __iter__(self):
        return iter(self.__players)


class SnarotGameTower:
    __collapsing: CardPile[SnarotCard]
    __tower: CardPile[SnarotCard]

    def __init__(self):
        self.__collapsing = CardPile()
        self.__tower = CardPile()

    def add_to_tower(self, card: SnarotCard):
        self.__tower.append(card)

    @property
    def collapsing(self) -> bool:
        return bool(self.__collapsing)

    def start_collapse(self):
        self.__collapsing, self.__tower = self.__tower, self.__collapsing

    def get_collapse(self, count: int = 2) -> list[SnarotCard]:
        return self.__collapsing.draw(count)


FieldColor = Literal["r", "g", "b", "y"]
FieldNumber = Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


class SnarotGameField:
    color: FieldColor
    number: FieldNumber

    def shuffle(self):
        self.color = cast(FieldColor, ["r", "g", "b", "y"][randint(0, 3)])
        self.number = cast(FieldNumber, randint(1, 10))

    def __init__(
        self,
        color: FieldColor | None = None,
        number: FieldNumber | None = None,
    ):
        self.shuffle()
        if color is not None:
            self.color = color
        if number is not None:
            self.number = number


class InvalidException(Exception):
    message: str

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class CardInvalidException(InvalidException):
    pass


class PlayerInvalidException(InvalidException):
    pass


class NotInTurnException(InvalidException):
    pass


class NeedColorPickException(Exception):
    index: int
    card: SnarotCard

    def __init__(self, index: int, card: SnarotCard):
        self.index = index
        self.card = card


@dataclass(frozen=True)
class FieldSnapshot:
    field_color: FieldColor
    field_number: FieldNumber
    collapsing: bool


@dataclass(frozen=True)
class TurnSnapshot:
    player_id: str
    hand: list[SnarotCard]
    usable: list[int]
    draw_hold: int
    draw_delay: int
    field: FieldSnapshot


class SnarotBotHooks:
    """
    Hooks 类
    用于在 bot 对接侧实现事件回调。
    游戏在触发特定事件时，会调用对应方法。
    """

    def on_draw(
        self,
        player_id: str,
        cards: list[SnarotCard],
        type: Literal["deal", "pass", "collapse", "attack", "self_draw"],
        # 开局发牌，过牌，巨塔崩塌，预言抽牌，预言自身抽牌
    ) -> None:
        """
        某位玩家被派发卡牌。type 指定派发的原因。
        Bot 向玩家私聊被派发的卡牌列表。
        """

    def on_play(
        self,
        player_id: str,
        card: SnarotCard | None,
        field: FieldSnapshot,
    ) -> None:
        """
        某位玩家行动。如果玩家没有打出卡牌，则 card 为 None。
        Bot 向群聊公告玩家的行动。
        """

    def on_collapse(self) -> None:
        """
        巨塔开始崩塌。
        Bot 向群聊公告。
        """

    def on_turn_start(
        self, player_id: str, turn: TurnSnapshot, turn_count: int, turn_timeout: int
    ) -> None:
        """
        轮到某位玩家。
        Bot 向玩家私聊当前的手牌与场地信息。
        """

    def on_turn_timeout(self, player_id: str) -> None:
        """
        某位玩家行动超时，回落到默认行动。
        Bot 向玩家私聊通知。
        """

    def on_need_color_pick(self, player_id: str, index: int, card: SnarotCard) -> None:
        """
        玩家准备打出需要选择场地颜色的卡牌。
        Bot 向玩家私聊提示选色。
        """

    def on_player_win(self, player_id: str, rank: list[tuple[str, int]]) -> None:
        """
        某位玩家打完了手牌，取得胜利。
        Bot 向群聊公告胜者和玩家按手牌数量的排名。
        """

    def on_draw_exceeded_end(
        self, draw_count: int, rank: list[tuple[str, int]]
    ) -> None:
        """
        从牌库中抽取的卡牌张数达到设定的结束数量，
        游戏结束。
        Bot 向群聊公告玩家按手牌数量的排名。
        """

    def on_not_ready(self, player_ids: list[str]) -> None:
        """
        仍有玩家未准备好时，尝试开始游戏。
        Bot 向群聊通知还未准备好的玩家列表。
        """

    def on_group_message(self, text: str) -> None:
        """
        通用：Bot 向群聊发送一段文本消息。
        """

    def on_private_message(self, player_id: str, text: str) -> None:
        """
        通用：Bot 向玩家私聊一段文本消息。
        """


class SnarotGameBase:
    players: SnarotGamePlayerManager
    tower: SnarotGameTower
    field: SnarotGameField
    card_pack: CardPile[SnarotCard]
    card_disposal: CardPile[SnarotCard]

    drawn_count: int = 0

    hooks: SnarotBotHooks

    def __init__(self, hooks: SnarotBotHooks):
        self.players = SnarotGamePlayerManager()
        self.tower = SnarotGameTower()
        self.field = SnarotGameField()
        self.card_pack = CardPile()
        self.card_disposal = CardPile()

        self.hooks = hooks

    def _player_precheck(self, player_id: str) -> SnarotPlayer:
        player = self.players.get_player(player_id)
        if player is None:
            raise PlayerInvalidException("错误：玩家不在对局内。")
        if self.players.get_current_player() != player:
            raise NotInTurnException("现在还不是你的回合哦。")
        return player

    def __check_card_usable(self, card: SnarotCard, player: SnarotPlayer) -> bool:
        if self.tower.collapsing:
            return card.clearAttack
        if card.applyColor == "u":
            return True
        if player.draw_hold != 0 and card.clearAttack:
            return True
        return bool(
            card.number == self.field.number or card.applyColor == self.field.color
        )

    def __run_card(
        self,
        card: SnarotCard,
        selected_color: FieldColor | None = None,
    ) -> list[Callable[[], None]]:

        change_hooks = []

        if card.reverse:
            self.players.reverse()

        curr_player = self.players.get_current_player()
        next_player = self.players.get_next_player()

        if selected_color is not None and card.updateColor == "s":
            self.field.color = selected_color
        if card.updateColor not in ["s", "n"]:
            self.field.color = card.updateColor
        if card.number != 0:
            self.field.number = card.number
        if card.clearAttack:
            curr_player.draw_hold = 0
            curr_player.draw_delay = 0
        if card.selfDraw > 0:
            drawed = self._pack_draw(card.selfDraw)
            curr_player.deck.extend(drawed)
            change_hooks.append(
                partial(self.hooks.on_draw, curr_player.id, drawed, "self_draw")
            )
        if card.disable:
            next_player.skip = True
        next_player.draw_hold = card.attackDraw
        next_player.draw_delay = card.attackDelay + 1
        if card.collapse:
            change_hooks.append(self.hooks.on_collapse)
            self.tower.start_collapse()

        return change_hooks

    def __player_enter_turn(self, player: SnarotPlayer):
        if player.skip:
            player.skip = False
            self.__proceed()
        else:
            if player.draw_delay > 0:
                player.draw_delay -= 1
            if player.draw_delay == 0 and player.draw_hold > 0:
                drawed = self._pack_draw(player.draw_hold)
                player.deck.extend(drawed)
                self.hooks.on_draw(player.id, drawed, "attack")
                player.draw_hold = 0

    def __proceed(self):
        self.players.proceed()
        self.__player_enter_turn(self.players.get_current_player())

    def _pack_draw(self, count: int) -> list[SnarotCard]:
        # 从此局游戏的牌库和弃牌堆抽牌。数量不够时抽完并返回。
        result: list[SnarotCard] = []
        while len(result) < count:
            if not self.card_pack:
                self.card_pack, self.card_disposal = self.card_disposal, self.card_pack
            drawn = self.card_pack.draw(count - len(result))
            if not drawn:
                break
            result.extend(drawn)
        self.drawn_count += len(result)
        return result

    def _deal(self, deck_size: int):
        for player in self.players:
            cards = self._pack_draw(deck_size)
            player.deck.extend(cards)
            self.hooks.on_draw(player.id, cards, "deal")

    def _get_field_snapshot(self) -> FieldSnapshot:
        return FieldSnapshot(
            field_color=self.field.color,
            field_number=self.field.number,
            collapsing=self.tower.collapsing,
        )

    def _get_turn_snapshot(self, player: SnarotPlayer) -> TurnSnapshot:
        return TurnSnapshot(
            player_id=player.id,
            hand=player.deck[:],
            usable=self._list_usable_cards(player),
            draw_hold=player.draw_hold,
            draw_delay=player.draw_delay,
            field=self._get_field_snapshot(),
        )

    def _list_usable_cards(self, player: SnarotPlayer) -> list[int]:
        return [
            index
            for index, card in enumerate(player.deck)
            if self.__check_card_usable(card, player)
        ]

    def play_card(
        self,
        player_id: str,
        card_index: int,
        selected_color: FieldColor | None = None,
    ):
        player = self._player_precheck(player_id)
        try:
            card = player.get_card(card_index)
        except IndexError:
            raise CardInvalidException("请指定数字范围内的卡牌。")
        if not self.__check_card_usable(card, player):
            raise CardInvalidException("此卡牌现在不能打出。")
        if card.updateColor == "s" and selected_color is None:
            raise NeedColorPickException(card_index, card)

        changes = self.__run_card(card, selected_color)
        if card.addToTower:
            self.tower.add_to_tower(card)
        else:
            self.card_disposal.append(card)
        player.delete_card(card_index)

        self.hooks.on_play(player.id, card, self._get_field_snapshot())
        for hook in changes:
            hook()

        self.__proceed()

    def pass_turn(self, player_id: str):
        player = self._player_precheck(player_id)
        if self.tower.collapsing:
            drawed = self.tower.get_collapse()
            player.deck.extend(drawed)
            self.hooks.on_draw(player.id, drawed, "collapse")
        else:
            drawed = self._pack_draw(1)
            player.deck.extend(drawed)
            self.hooks.on_draw(player.id, drawed, "pass")
        self.hooks.on_play(player.id, None, self._get_field_snapshot())

        self.__proceed()


class SnarotGame(SnarotGameBase):
    turn_timeout: int = 0
    __timeout_task: asyncio.Task | None

    max_drawn_count: int

    started: bool = False
    ended: bool = False

    __turn_count: int = 0
    __pending_select_color: tuple[int, int] | None

    @property
    def turn_count(self) -> int:
        return self.__turn_count

    def __init__(
        self, hooks: SnarotBotHooks, turn_timeout: int = 0, max_drawn_count: int = 80
    ):
        self.__timeout_task = None
        self.max_drawn_count = max_drawn_count
        if turn_timeout > 0:
            try:
                asyncio.get_running_loop()
                self.turn_timeout = turn_timeout
            except RuntimeError:
                print("无法使用回合超时功能，请在 asyncio 上下文中运行。")
                print("回合超时将不会触发。")
        super().__init__(hooks)

    def __check_winner(self):
        winner = self.players.get_winner()
        if winner is not None:
            self.ended = True
            self.hooks.on_player_win(winner.id, self.players.get_rank())
        elif self.drawn_count >= self.max_drawn_count:
            self.ended = True
            self.hooks.on_draw_exceeded_end(self.drawn_count, self.players.get_rank())

    def __begin_player(self, player: SnarotPlayer):
        self.__check_winner()
        if self.ended:
            self.__cancel_timeout()
            return

        turn_count = self.__turn_count + 1
        self.__turn_count = turn_count

        self.__cancel_timeout()
        if self.turn_timeout > 0:
            self.__timeout_task = asyncio.create_task(
                self.__timeout_checker(player.id, turn_count)
            )

        self.hooks.on_turn_start(
            player.id,
            self._get_turn_snapshot(player),
            self.turn_count,
            self.turn_timeout,
        )

    async def __timeout_checker(self, player_id: str, turn_count: int):
        try:
            await asyncio.sleep(self.turn_timeout)
        except asyncio.CancelledError:
            return
        if not self.ended and self.turn_count == turn_count:
            self.__timeout_task = None
            self.hooks.on_turn_timeout(player_id)
            self.handle_pass(player_id)

    def __cancel_timeout(self) -> None:
        task = self.__timeout_task
        if task is not None and not task.done():
            task.cancel()
        self.__timeout_task = None

    def force_shutdown(self) -> None:
        self.ended = True
        self.__cancel_timeout()

    def handle_prepare(self, player_id: str):
        player = self.players.get_player(player_id)
        if player is not None:
            player.ready = True

    def handle_start_game(self, deck_size: int = 7):
        if self.started:
            return
        if len(self.players) < 2:
            self.hooks.on_group_message("玩家的人数不足，无法开始游戏")
            return
        not_ready = self.players.get_not_ready()
        if len(not_ready) > 0:
            self.hooks.on_not_ready(not_ready)
            return
        if len(self.card_pack) < len(self.players) * deck_size:
            self.hooks.on_group_message("牌库中的卡牌数量不足，无法开始游戏")
            return
        self._deal(deck_size)
        self.started = True
        self.__begin_player(self.players.get_current_player())

    # 回合循环逻辑
    def __round_handler(self, player_id: str, action: Callable[[], None]) -> None:
        if not self.started:
            self.hooks.on_private_message(player_id, "游戏还没有开始哦")
            return
        if self.ended:
            return
        try:
            action()
            self.__pending_select_color = None
            self.__begin_player(self.players.get_current_player())
        except NeedColorPickException as e:
            self.__pending_select_color = (e.index, self.turn_count)
            self.hooks.on_need_color_pick(player_id, e.index, e.card)
        except InvalidException as e:
            self.hooks.on_private_message(player_id, e.message)

    def handle_pass(self, player_id: str):
        self.__round_handler(player_id, partial(self.pass_turn, player_id))

    def handle_play(
        self,
        player_id: str,
        card_index: int,
        selected_color: FieldColor | None = None,
    ):
        self.__round_handler(
            player_id, partial(self.play_card, player_id, card_index, selected_color)
        )

    def select_color(self, player_id: str, selected_color: FieldColor):
        self._player_precheck(player_id)
        if self.__pending_select_color is None:
            raise InvalidException("目前不需要指定颜色。")
        (pending_index, pending_turn_count) = self.__pending_select_color
        self.__pending_select_color = None
        if pending_turn_count != self.turn_count:
            raise InvalidException("目前不需要指定颜色。")
        self.play_card(player_id, pending_index, selected_color)

    def handle_select_color(self, player_id: str, selected_color: FieldColor):
        self.__round_handler(
            player_id, partial(self.select_color, player_id, selected_color)
        )

    def handle_add_player(self, player_id: str) -> bool:
        if not self.started:
            try:
                self.players.add_player(player_id)
                self.hooks.on_group_message("加入成功")
                return True
            except PlayerOpException:
                self.hooks.on_group_message("你已经在这局游戏内了")
                return False
        else:
            self.hooks.on_group_message("游戏已开始，不能加入")
            return False

    def handle_remove_player(self, player_id: str):
        if not self.started:
            try:
                self.players.remove_player(player_id)
                self.hooks.on_group_message("你已退出游戏")
                return True
            except PlayerOpException:
                self.hooks.on_group_message("你还没有加入游戏")
                return False
        else:
            self.hooks.on_group_message("游戏已开始，不能退出")
            return False


class SnarotBot(SnarotBotHooks):
    game: SnarotGame | None = None

    def attach(self, game: SnarotGame):
        self.game = game
