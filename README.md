# Messages
**States**:

- 0 - Waiting for connection;  
- 1 - Select the first player to choose the word;  
- 2 - Receiving attempts from the player who is trying to guess the word and sending the responses to the other player. This state occurs twice — on the second time, the roles are reversed;  
- 3 - Players deciding whether to play again. If both choose to play again, go to state 1. If both choose to quit, terminate. If only one wants to play again, return to state 0 to wait for another connection.

**Messages**:

- 0 - Connections;  
- 1 - Request: operation ID only, 1 byte. Response: the chosen word (bytes corresponding to the string length);  
- 2 - Request: operation ID, 1 byte; chosen letter as a byte (char-sized). Response: 1 byte set to 0 if incorrect, or 1 byte set to 1 if correct, followed by the positions of the correct letters;  
- 3 - Request: operation ID, 1 byte. Response: 1 byte set to 0 if incorrect, the letter the other player guessed, 1 byte set to 0 if incorrect, or 1 byte set to 1 if correct, followed by the positions of the correct letters;  
- 4 - Request: operation ID, 1 byte; second byte set to 0 if the player wants to disconnect or 1 if they want to continue playing.

![{15D8811D-4E0E-4126-9995-8D96178DC20B}](https://github.com/user-attachments/assets/dd982940-bf43-44b1-9767-7ff657565a93)


## Commands
In separated terminals
```sh
python3 -m venv venv
source venv/bin/activate
# terminal 1
python3 server.py
# terminal 2
python3 client.py
# terminal 3
python3 client.py
```
  
