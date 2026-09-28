# Chapter 2 — State-Driven Agent Design

Run:
- `uv run python -m gameai.ch02_state_machines` — West World in a window (states, dialogue, telegrams in flight)
- `uv run python -m gameai.ch02_state_machines.westworld1` — first version, console
- `uv run python -m gameai.ch02_state_machines.westworld` — final version, console

## Book sections → code

| Book section | Code |
|---|---|
| Implementing an FSM (switch, transition tables, embedded rules) | Discussion only |
| The West World project: `BaseGameEntity`, `Miner`, the Miner states | `ch02_state_machines.westworld1` (C++ `WestWorld1`) |
| The State Design Pattern Revisited (singleton states) | Module-level state instances, e.g. `ENTER_MINE_AND_DIG_FOR_NUGGET` |
| Making the State Base Class Reusable | `gameai.common.fsm.State[Owner]` |
| Global States and State Blips | `StateMachine.global_state`, `revert_to_previous_state`; `WifesGlobalState`, `VisitBathroom`, `EatStew` |
| Creating a State Machine Class | `gameai.common.fsm.StateMachine[Owner]` |
| Introducing Elsa | `westworld.wife` (C++ `WestWorldWithWoman`) |
| Adding Messaging: `Telegram`, dispatch and management | `gameai.common.messaging`: `Telegram`, `MessageDispatcher`, `EntityRegistry` |
| Message Handling; Elsa Cooks Dinner (steps 1–5) | `State.on_message`, `CookStew`, `GoHomeAndSleepTilRested.on_message` (C++ `WestWorldWithMessaging`) |

`WestWorldWithWoman` is a strict subset of `WestWorldWithMessaging`, so only the first and final
versions are ported. `westworld1` keeps the "before" design on purpose: its `MinerState` works
only with `Miner`, and the miner changes its own state.

## C++ → Python

| C++ | Python |
|---|---|
| `State<entity_type>` with pure virtual `Enter/Execute/Exit/OnMessage` | `State[Owner]` with no-op defaults: override only what you need |
| `static State* Instance()` singletons | one module-level instance per state class |
| `StateMachine<T>::SetCurrentState/SetGlobalState` | constructor arguments `current=`, `global_state=` |
| `isInState(*VisitBathroom::Instance())` (`typeid`) | `fsm.is_in_state(VisitBathroom)` (`isinstance`) |
| `GetNameOfCurrentState()` | `fsm.current.name` |
| `EntityMgr` singleton | `EntityRegistry`, owned by the world |
| `Dispatch` singleton, `DispatchMsg(delay, sender, receiver, msg, info)` | `world.dispatcher.dispatch(msg, sender, receiver, delay, extra)` |
| `std::set<Telegram>` sorted by time, `operator==` with `SmallestDelay` | `heapq` + explicit duplicate check (`Telegram.duplicates`) |
| `Clock` (`CrudeTimer`) singleton | injected `Clock` (`() -> float`); `ManualClock` in the simulation and tests |
| `enum message_type` + `MsgToStr` | `Message(Enum)`: the name comes for free |
| `SetTextColor` + `cout` | a `Narrator` callable receiving `(line, Tone)`: console with ANSI colors, a list in tests, a log in the window |
| `ExtraInfo` (`void*`) + `DereferenceToType<T>` | `extra: Any` |

## Design decisions and deviations

- **No singletons.** The C++ code reaches the entity manager, dispatcher and clock through
  globals. Here the `WestWorld` owns them and agents reach them through `agent.world`. The
  states themselves remain shared, stateless instances, as in the book.
- **Simulated time.** The world advances a `ManualClock` by 0.8 s per tick instead of sleeping and
  reading the wall clock, so runs are reproducible (`create_world(seed=...)`) and the
  console versions only sleep for show.
- **Plain attributes** replace getters/setters (`miner.location = Location.BANK`); methods remain
  only where there is logic (`pockets_full`, `thirsty`, `buy_and_drink_whiskey`, ...).
- **`match` on the message** replaces `switch(msg.Msg)`.
- **C++ bug not ported:** `MsgToStr` maps 1 and 2, but the enum values are 0 and 1, so
  `Msg_HiHoneyImHome` prints as "Not recognized!". Python enums carry their names.
- **Faithful quirks, kept on purpose** (they are good lessons):
  - A state blip still runs `exit`/`enter`. If Elsa goes to the bathroom while cooking,
    `CookStew.exit` says "Puttin' the stew on the table" too early and says it again when the
    stew is really ready. The C++ output does the same.
  - `EnterMineAndDigForNugget.execute` can change state twice in one update (pockets full,
    then thirsty); the second change wins and the bank visit is skipped.
  - If Bob isn't sleeping at home when `StewReady` arrives, no state handles it and he never
    eats.

## Tests

`tests/common/test_fsm.py` and `test_messaging.py` cover the reusable pieces (exit/enter
order, blips, message routing, delayed delivery, duplicate suppression);
`tests/ch02_state_machines/test_westworld.py` plays out the book's scenes: Bob's first
update, the bank and saloon trips, "Elsa cooks dinner" end to end with the delayed
`StewReady`, and the bathroom blip.
