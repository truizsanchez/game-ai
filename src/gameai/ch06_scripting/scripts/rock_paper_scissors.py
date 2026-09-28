# Rock-paper-scissors: the game loop lives in the script, the rules in the host
# (C++ lua_using_cpp/Rock_Paper_Scissors_Using_C++_Funcs.lua).
#
# Provided by the host: get_ai_move(), evaluate_the_guesses(), read_line()

POSSIBLE_MOVES = {"s": "scissors", "r": "rock", "p": "paper"}

user_score = 0
comp_score = 0


def play():
    global user_score, comp_score
    while True:
        print(f"\nUser: {user_score} Computer: {comp_score}")
        print("Input your guess r/p/s  [enter q to quit]")
        user_guess = read_line()
        if user_guess == "q":
            return
        if user_guess in POSSIBLE_MOVES:
            comp_guess = get_ai_move()
            user_score, comp_score = evaluate_the_guesses(
                POSSIBLE_MOVES[user_guess], comp_guess, user_score, comp_score
            )
        else:
            print("Invalid input, try again")
