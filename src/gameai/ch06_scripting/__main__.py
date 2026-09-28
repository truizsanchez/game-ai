"""Chapter 6 examples.

python -m gameai.ch06_scripting            # scripted miner in a window, hot reloading
python -m gameai.ch06_scripting miner      # the same in the console
python -m gameai.ch06_scripting hello | globals | rps | functions | classes | script-classes
"""

import argparse
import time

from gameai.ch06_scripting import examples
from gameai.ch06_scripting.scripted_fsm import ScriptedMiner

EXAMPLES = {
    "hello": examples.start_here,
    "globals": examples.host_reads_script,
    "rps": examples.rock_paper_scissors,
    "functions": examples.exposing_functions,
    "classes": examples.exposing_classes,
    "script-classes": examples.classes_in_script,
}

parser = argparse.ArgumentParser(prog="python -m gameai.ch06_scripting", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)  # fmt: skip
parser.add_argument("example", nargs="?", choices=[*EXAMPLES, "miner", "window"], default="window")
args = parser.parse_args()

if args.example == "window":
    from gameai.ch06_scripting.demo import ScriptedMinerDemo
    from gameai.common.view import run

    run(ScriptedMinerDemo, title="Chapter 6: To Script, or Not to Script")
elif args.example == "miner":
    miner = ScriptedMiner("Bob", examples.script_path("miner_states.py"))
    print(f"Edit {miner.fsm.script.path} while this runs (Ctrl+C to stop)")
    while True:
        if miner.update():
            print("---- script reloaded ----")
        time.sleep(0.8)
else:
    EXAMPLES[args.example]()
