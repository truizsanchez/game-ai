# Calling functions the host exposed
# (C++ ExposingCPPFunctionsUsingLuabind/ExposingCPPFunctionsToLua.lua).
#
# Provided by the host: hello_world(), add()

print("[script]: About to call the host's hello_world() function")
hello_world()

print("\n[script]: About to call the host's add() function")
a = 10
b = 5
print(f"\n[script]: {a} + {b} = {add(a, b)}")
