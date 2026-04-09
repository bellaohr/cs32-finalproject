''' because I'm doing client and server, not sure how to do this...
'''

def updated_blur_state(current_blur_state, answer, guess):
    state = list(current_blur_state)
    result = []

    for i in range(len(answer)):
        if guess[i] == answer[i]:
            state[i] = answer[i]

    return updated_blur_state




