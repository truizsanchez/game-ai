# Miner Bob's states, loaded at runtime (C++ ScriptedStateMachine/StateMachineScript.lua).
#
# Each state is an object with enter/execute/exit methods. The state machine refers to
# states by the name of the global that holds them ("go_home", "sleep", ...), so editing
# and saving this file while the miner runs changes his behavior on the next update.
#
# Provided by the host: say(text)


class GoHome:
    def enter(self, miner):
        say("Walkin' home in the hot n' thusty heat of the desert")

    def execute(self, miner):
        say("Back at the shack. Yes siree!")
        if miner.fatigued:
            miner.fsm.change_state("sleep")
        else:
            miner.fsm.change_state("go_to_mine")

    def exit(self, miner):
        say("Puttin' mah boots on n' gettin' ready for a day at the mine")


class Sleep:
    def enter(self, miner):
        say(f"Miner {miner.name} is dozin' off")

    def execute(self, miner):
        if miner.fatigued:
            say("ZZZZZZ... ")
            miner.fatigue -= 1
        else:
            miner.fsm.change_state("go_to_mine")

    def exit(self, miner):
        say(f"Miner {miner.name} is feelin' mighty refreshed!")


class GoToMine:
    def enter(self, miner):
        say(f"Miner {miner.name} enters the goldmine")

    def execute(self, miner):
        miner.fatigue += 1
        miner.gold_carried += 2
        say(f"Miner {miner.name} has got {miner.gold_carried} nuggets")
        if miner.gold_carried > 4:
            say(f"Miner {miner.name} decides to go home, with his pockets full of nuggets")
            miner.fsm.change_state("go_home")

    def exit(self, miner):
        say(f"Miner {miner.name} exits the goldmine")


go_home = GoHome()
sleep = Sleep()
go_to_mine = GoToMine()
