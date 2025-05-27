# Messages
**States**:

- 0 - Waiting for connection;  
- 1 - Select the first player to choose the word;  
- 2 - Receiving attempts from the player who is trying to guess the word and sending the responses to the other player. This state occurs twice — on the second time, the roles are reversed;  
- 3 - Players deciding whether to play again. If both choose to play again, go to state 1. If both choose to quit, terminate. If only one wants to play again, return to state 0 to wait for another connection.

**Messages**:

- 0 - Connections;  
- 1 - Setter to Server (OP_SETWORD): Opcode 1; word length (1 byte), chosen word (ASCII string).
- 2 - Guesser to Server (OP_GUESS): Opcode 2; guessed letter (1 char byte).
- 3 - Server to Setter (OP_UPDATE): Opcode 3; opponent's guessed letter (1 char byte), correctness (1 byte: 0/1), positions of correct letters (if any).
- 4 - Client to Server (OP_RESTART): Opcode 4; decision flag (1 byte: 0 to disconnect, 1 to continue playing).
- 5 - Server to Guesser (OP_START): Opcode 5; word length (1 byte).
- 6 - Server to Guesser (OP_GAME_OVER_WIN): Opcode 6; word length (1 byte), the winning word (ASCII string).
- 7 - Server to Guesser (OP_GAME_OVER_LOSE): Opcode 7; word length (1 byte), the actual word (ASCII string).
- 8 - Server to Client (OP_PLAYER_ROLE): Opcode 8; role ID (1 byte: 1 for Setter, 2 for Guesser).
- 9 - Server to Client (OP_GAME_STATE): Opcode 9; current word display (length byte + ASCII string), wrong guesses (length byte + ASCII string), remaining attempts (1 byte), turn flag (1 byte for guesser).
- 11 - Server to Setter (OP_OPPONENT_WON): Opcode 11; word length (1 byte), the guessed word (ASCII string).
- 12 - Server to Setter (OP_OPPONENT_LOST): Opcode 12; word length (1 byte), the actual word (ASCII string).
- 13 - Server to Client (OP_RESTART_CONFIRM): Opcode 13; confirmation flag (1 byte: 1 to continue, 0 to end session).
- 14 - Server to Client (OP_WAITING_FOR_PLAYER): Opcode 14; status payload (1 byte, e.g., 0 for waiting).

![{57F89396-0B6C-44B7-98E4-99625DDAF69A}](https://github.com/user-attachments/assets/810ee6f9-919c-4906-8264-ff6a5fafa2d4)



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
  
