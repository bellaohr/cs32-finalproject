''' because I'm doing client and server, not sure how to do this...
'''

def updated_blur_state(current_blur_state, answer, guess):
    state = list(current_blur_state) #converts current_blur_state into a list that's stored in state

    for i in range(len(answer)): #loops thru each index of the word
        if guess[i] == answer[i]: #checks if player guess matches word @ given index
            state[i] = answer[i] #if they match, replace * with the letter

    return state




