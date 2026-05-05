# cs32-finalproject
FINAL CS32 FP README:

For my final project, I've created a two-player networked game. I modeled this game off of the New York Times Wordle game, however instead of getting a "random" word, this game involves to players: the "word-setter" and the "guesser."

The "word-setter" will select a secret 4-6 letter word that can only include characters in the English alphabet. The "guesser"  will recieve a display of tiles that corresponds to the number of letters in the word the other player has selected and will need to guess the word. If the "guesser" gets a letter in the correct spot, the tile will turn green. If the letter is in the wrong spot but is in the "word-setter's" word, it will appear yellow. Finally, the letter will be gray if it isn't in the word at all. The keyboard at the bottom of the display will be colored accordingly to make sure the "guesser" has access to the letters they have already used


HOW TO RUN THE CODE:
In order to run the code, the user will need to download flask, which is done buy imputting the following into the terminal: pip3 install flask --break-system-packages (I got this from Claude)

Next, the person must begin by opening three terminals in VS code:
1) Start the game server by imputting python3 server.py
2) Start the first player's client server by running python3 client1.py
3) Start the second player's client server by running python3 client2.py
4) Player 1 should open http://localhost:5000 in Chrome
5) Player 2 should open http://localhost:5001 in Chrome
Technically the scripts client1 and client2 are the same except for which ports they use, so it doesn't matter what order they are run, it just is important to know that client1 script uses port 5000 while client2 uses port 5001.

An error that came up rather frequently was the "port already in use" error so if that comes up run the following command in your terminal: lsof -ti:65434 | xargs kill -9 (I also got this from Claude)


GAI USAGE:
I used Claude to troubleshoot the connection and port errors I was having. During this part of the project, I focused on editing the client script and figured out that it needed to be split into two to make it easier for the users as it previously required to changing the code then running it to differentiate the two players.
Claude wrote the part of the code that made the HTML browser possible, in addition to the Flask server structure. I will go into how I used it more in depth in my video!






















ReadMe as of FP status (4/23)
I am hoping to make a guess the word game where a player picks a word between 4-6 letters and the other player has to guess it. I'm planning on creating a similar thing to the final part of the roshambo PSet where the client and server were two players playing against each other. I'm hoping that the server will choose the word and the client will guess it. Ideally, I would want the word to be completely blurred out (i.e. cats would become ****) and have a printed statement that says "X words are in the correct spot" or "X words are in the wrong spot." If possible, I would want to put the word in the correct spot into the blurred out statement (i.e. if the guess was dark, the statement would become *a**)

The subtask I choose to do is the finding the letter in the correct spot and making sure it is printed out in the subsequent guesses! I think I would need to slice both the word and the guess, index (e.g. if guess[2] and answer[2] are the same) then find a way to reveal just that part of the word.

4/23 UPDATE: (FP STATUS)
- before the client was waiting to recieve a message that started with INPUT: before it even let the player type anything, in this version i updated the server code so that it distinguishes between IMPUTs from player 1 and other messages
- i heard i was supposed to do something different than what i did from class so instead of having a client as one player and server as another, i put both players into the server so now there are 3 open terminals!
As of now, the game works so there are 2 players and one player is the wordsetter and the other is the guesser. the wordsetter sets a 4-6 character word that is then hidden via starts that correspond to the number of characters in that word. the player 2 then has to guess the word and letters in the correct spot are revealed while the letters that are in the wrong spot are just noted that they are in the wrong spot.

POTENTIAL NEXT STEP: Only letting actual words be used (or make it a secret code game instead and have a different display)
