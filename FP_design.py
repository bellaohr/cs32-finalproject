''' because I'm doing client and server, not sure how to do this...
'''

def updated_blur_state(current_blur_state, secret, guess):
    revealed = list(current_blur_state) #converts current_blur_state into a list that's stored in state

    for i in range(len(secret)): #loops thru each index of the word
        if guess[i] == secret[i]: #checks if player guess matches word @ given index
            revealed[i] = guess[i] #if they match, replace * with the letter
            correct_spot += 1

    return revealed







