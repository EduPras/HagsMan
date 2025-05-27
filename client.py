import socket
import logging
import os

from server import OP_WAITING_FOR_PLAYER

# Configuração de logs
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(levelname)s %(message)s',
    datefmt='%H:%M:%S'
)

HOST = 'localhost'
PORT = 12345

# Opcodes (Certifique-se de que o servidor use os mesmos valores)
OP_SETWORD         = 1
OP_GUESS           = 2
OP_UPDATE          = 3
OP_RESTART         = 4
OP_START           = 5
OP_GAME_OVER_WIN   = 6
OP_GAME_OVER_LOSE  = 7
OP_PLAYER_ROLE     = 8
OP_GAME_STATE      = 9
OP_OPPONENT_WON    = 11
OP_OPPONENT_LOST   = 12
OP_RESTART_CONFIRM = 13
OP_WAITING_FOR_PLAYER = 14

def recv_exact(sock, n):
    buf = b''
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Conexão encerrada pelo servidor")
        buf += chunk
    logging.debug(f"Recebido {buf!r}")
    return buf

def display_game_state(word_display, wrong_guesses, remaining_attempts):
    clear_screen()
    print("\n" + "="*30)
    print(f"📖 Palavra: {' '.join(word_display)}")
    print(f"❌ Letras erradas: {' '.join(sorted(list(wrong_guesses)))}")
    print(f"❤️ Tentativas restantes: {remaining_attempts}")
    print("="*30)

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((HOST, PORT))
        logging.info("Conectado ao servidor.")

        # Variáveis de estado do jogo no cliente
        current_word_display = []
        wrong_guesses = set()
        remaining_attempts = 0
        is_setter = False

        while True: # Loop principal do cliente para gerenciar múltiplos jogos/reinícios
            logging.debug("Esperando opcode do servidor...")
            op = recv_exact(s, 1)[0]
            logging.debug(f"Opcode {op} recebido")

            if op == OP_PLAYER_ROLE:
                role_byte = recv_exact(s, 1)[0]
                if role_byte == 1:
                    is_setter = True
                    clear_screen()
                    print("\nVocê é o SETTER (quem escolhe a palavra).")
                    word = ""
                    while not word or not word.isalpha():
                        word = input("🔒 Digite a palavra secreta: ").strip().lower()
                        if not word.isalpha() or len(word) == 0:
                            print("A palavra deve conter apenas letras e não pode ser vazia. Tente novamente.")
                    s.sendall(bytes([OP_SETWORD, len(word)]) + word.encode('ascii'))
                    logging.debug(f"Enviou palavra '{word}'")
                    print("Palavra enviada. Aguardando o GUESSER começar...")
                elif role_byte == 2:
                    is_setter = False
                    clear_screen()
                    print("\nVocê é o GUESSER (quem adivinha a palavra).")
                    print("Aguardando o SETTER definir a palavra e o jogo começar...")
                else:
                    logging.warning(f"Tipo de papel desconhecido recebido: {role_byte}")

            elif op == OP_START:
                length = recv_exact(s, 1)[0]
                current_word_display = ['_'] * length
                wrong_guesses = set()
                remaining_attempts = 6

                # O OP_START apenas informa o início, o OP_GAME_STATE fará a primeira exibição completa.
                logging.debug(f"OP_START: length={length}")

            elif op == OP_GAME_STATE:
                len_word_display = recv_exact(s, 1)[0]
                word_display_bytes = recv_exact(s, len_word_display)
                current_word_display = list(word_display_bytes.decode('ascii'))

                len_wrong_guesses = recv_exact(s, 1)[0]
                wrong_guesses_bytes = recv_exact(s, len_wrong_guesses)
                wrong_guesses = set(wrong_guesses_bytes.decode('ascii'))

                remaining_attempts = recv_exact(s, 1)[0]

                is_my_turn_flag = recv_exact(s, 1)[0]

                display_game_state(current_word_display, wrong_guesses, remaining_attempts)

                if is_setter:
                    print("Aguardando a jogada do GUESSER...")
                    continue # Volta para esperar o próximo opcode

                if is_my_turn_flag == 1:
                    guess = ''
                    while len(guess) != 1 or not guess.isalpha() or guess in wrong_guesses or guess in current_word_display:
                        guess = input("Sua vez. Digite uma letra: ").strip().lower()
                        if guess in wrong_guesses or guess in current_word_display: # Validação local de letra já tentada
                            print(f"A letra '{guess}' já foi tentada ou está na palavra. Tente outra.")
                            guess = ''
                    s.sendall(bytes([OP_GUESS]) + guess.encode('ascii'))
                    logging.debug(f"Enviou palpite '{guess}'")
                else:
                    print("Aguardando a vez do outro jogador...")

            elif op == OP_GAME_OVER_WIN:
                final_word_len = recv_exact(s, 1)[0]
                final_word = recv_exact(s, final_word_len).decode('ascii')
                clear_screen()
                print("\nPARABÉNS! VOCÊ ADIVINHOU A PALAVRA! 🎉")
                print(f"A palavra era: {final_word.upper()}")

            elif op == OP_GAME_OVER_LOSE:
                final_word_len = recv_exact(s, 1)[0]
                final_word = recv_exact(s, final_word_len).decode('ascii')
                clear_screen()
                print("\nVOCÊ PERDEU! 😭")
                print(f"A palavra era: {final_word.upper()}")


            elif op == OP_OPPONENT_WON:
                final_word_len = recv_exact(s, 1)[0]
                final_word = recv_exact(s, final_word_len).decode('ascii')
                clear_screen()
                print("\nO GUESSER ADIVINHOU A PALAVRA! 😥")
                print(f"A palavra era: {final_word.upper()}")


            elif op == OP_OPPONENT_LOST:
                final_word_len = recv_exact(s, 1)[0]
                final_word = recv_exact(s, final_word_len).decode('ascii')
                clear_screen()
                print("\nO GUESSER NÃO ADIVINHOU A PALAVRA. 😜")
                print(f"A palavra era: {final_word.upper()}")


            elif op == OP_RESTART:
                # O servidor envia OP_RESTART com flag 1 (pedindo decisão) ou 0 (confirmando encerramento/reinício)
                restart_ask_flag = recv_exact(s, 1)[0]
                if restart_ask_flag == 1: # Servidor está perguntando se quer reiniciar
                    ans = input("Jogar de novo? (1=sim / 0=não): ").strip()
                    response_flag = 1 if ans == '1' else 0
                    s.sendall(bytes([OP_RESTART, response_flag]))
                    logging.debug(f"Respondeu restart={response_flag}")
                else:
                    logging.warning(f"Recebeu OP_RESTART com flag inesperada: {restart_ask_flag}. Deveria ser 1 (pergunta).")
                    break

            elif op == OP_RESTART_CONFIRM:
                confirm_flag = recv_exact(s, 1)[0]
                if confirm_flag == 1:
                    print("\nO servidor confirmou o reinício. Nova rodada começando!")
                elif confirm_flag == 0:
                    print("\nO servidor confirmou o encerramento da sessão. Encerrando.")
                    break

            elif op == OP_WAITING_FOR_PLAYER:
                print("Aguardando por outro jogador para iniciar a partida...")


            elif op == OP_UPDATE:
                logging.warning("Recebeu OP_UPDATE. O servidor deveria estar enviando OP_GAME_STATE.")
                # Tenta consumir os bytes do OP_UPDATE para não bagunçar o fluxo
                recv_exact(s, 1) # letter
                recv_exact(s, 1) # flag
            else:
                logging.warning(f"Opcode desconhecido: {op}")

    except ConnectionError as e:
        logging.error(f"Conexão caiu: {e}")
    except Exception as e:
        logging.error(f"Ocorreu um erro inesperado: {e}")
        logging.exception("Detalhes do erro:")
    finally:
        s.close()
        logging.info("Cliente encerrado.")

if __name__ == '__main__':
    main()