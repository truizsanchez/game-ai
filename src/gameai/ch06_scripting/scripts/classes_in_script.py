# Classes defined by the script, which the host can then instantiate
# (C++ CreatingClassesUsingLuabind/classes_in_lua.lua).


class Animal:
    def __init__(self, num_legs, noise_made):
        self.noise_made = noise_made
        self.num_legs = num_legs

    def speak(self):
        print(self.noise_made)


class Pet(Animal):
    def __init__(self, name, num_legs, noise_made):
        super().__init__(num_legs, noise_made)
        self.name = name


cat = Animal(4, "meow")
cat.speak()
print(f"a cat has {cat.num_legs} legs")

dog = Pet("Albert", 4, "woof")
dog.speak()
print(f"my dog's name is {dog.name}")
