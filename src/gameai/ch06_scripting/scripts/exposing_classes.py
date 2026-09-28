# Using classes the host exposed
# (C++ ExposingCPPClassesUsingLuabind/ExposingCPPClassesToLua.lua).
#
# Provided by the host: Animal, Pet

cat = Animal("Meow", 4)
print(f"\n[script]: A cat has {cat.num_legs} legs.")
cat.speak()

print("\n\n----------------------------------------------------")
my_pet = Pet("Scooter", "Meow", 4)
print(f"\n[script]: My pet is called {my_pet.name}")
my_pet.speak()
