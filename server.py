import socket
import threading
import time
import logging
import random

# Configuração do logger
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(levelname)s %(message)s',
    datefmt='%H:%M:%S'
)

HOST = '0.0.0.0'
PORT = 12345

# Opcodes (Certifique-se de que o cliente use os mesmos valores)
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

MAX_ERRORS = 6
TIMEOUT    = 60


def sendall_safe(sock, data: bytes):
    try:
        if sock.fileno() == -1: # Verifica se o socket ainda está aberto
            logging.warning(f"Tentativa de enviar para socket fechado: {sock.getpeername()}")
            return False
        sock.sendall(data)
        logging.debug(f"Enviado {data!r} para {sock.getpeername()}")
        return True
    except Exception as e:
        logging.warning(f"Falha ao enviar para {sock.getpeername()}: {e}")
        return False

def recv_exact(sock, n: int) -> bytes:
    buf = b''
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Conexão fechada pelo cliente")
        buf += chunk
    logging.debug(f"Recebido {buf!r} de {sock.getpeername()}")
    return buf

def send_game_state(guesser_sock, setter_sock, current_word_display, wrong_guesses_set, remaining_attempts, is_guesser_turn):
    word_display_str = "".join(current_word_display)
    wrong_guesses_str = "".join(sorted(list(wrong_guesses_set)))

    base_data = bytes([OP_GAME_STATE])
    base_data += bytes([len(word_display_str)]) + word_display_str.encode('ascii')
    base_data += bytes([len(wrong_guesses_str)]) + wrong_guesses_str.encode('ascii')
    base_data += bytes([remaining_attempts])

    guesser_data = base_data + bytes([1 if is_guesser_turn else 0])
    sendall_safe(guesser_sock, guesser_data)

    setter_data = base_data + bytes([0]) # Sempre 0 para o Setter, pois ele não chuta
    sendall_safe(setter_sock, setter_data)


def play_round(setter_sock, guesser_sock, players_data):
    """
    Gerencia uma única rodada do jogo (um SETTER, um GUESSER).
    Retorna True se a rodada foi jogada e os jogadores querem reiniciar, False se houve erro ou não querem.
    """
    try:
        # Atribuição de papéis (enviada novamente em cada rodada para reiniciar estado do cliente)
        sendall_safe(setter_sock, bytes([OP_PLAYER_ROLE, 1])) # 1 para SETTER
        sendall_safe(guesser_sock, bytes([OP_PLAYER_ROLE, 2])) # 2 para GUESSER
        logging.debug(f"Player {players_data[setter_sock]['id']} é o SETTER. Player {players_data[guesser_sock]['id']} é o GUESSER.")

        # 1) SETTER escolhe a palavra
        logging.debug("Esperando OP_SETWORD do SETTER.")
        word = ""
        while not word:
            setter_sock.settimeout(TIMEOUT)
            op_byte_word = recv_exact(setter_sock, 1)[0]

            if op_byte_word == OP_SETWORD:
                word_len_byte = recv_exact(setter_sock, 1)[0]
                word_bytes = recv_exact(setter_sock, word_len_byte)
                word = word_bytes.decode('ascii').lower()

                if word.isalpha() and len(word) > 0: # Garante que a palavra não é vazia
                    logging.debug(f"Player{players_data[setter_sock]['id']} escolheu: '{word}'")
                    break
                else:
                    logging.warning(f"Palavra inválida recebida: '{word}'. Pedindo novamente.")
                    sendall_safe(setter_sock, bytes([OP_PLAYER_ROLE, 1])) # Pede para o setter de novo (induz novo input no cliente)
                    word = "" # Resetar para continuar o loop
            else:
                logging.warning(f"Opcode inesperado ({op_byte_word}) do SETTER, esperando OP_SETWORD.")
                raise ConnectionError("Protocolo inesperado do SETTER")
        setter_sock.settimeout(None)

        word_len = len(word)
        hidden_word_list = ['_' if c.isalpha() else c for c in word]
        guessed_letters_set = set()
        wrong_guesses_set = set()
        errors = 0

        sendall_safe(guesser_sock, bytes([OP_START, word_len]))
        logging.debug(f">> OP_START enviado ao guesser com length={word_len}")

        send_game_state(guesser_sock, setter_sock, hidden_word_list, wrong_guesses_set, MAX_ERRORS - errors, True)

        while '_' in hidden_word_list and errors < MAX_ERRORS:
            logging.debug(f"Aguardando OP_GUESS do GUESSER ({players_data[guesser_sock]['id']}).")

            guesser_sock.settimeout(TIMEOUT)
            hdr = recv_exact(guesser_sock, 2)
            guesser_sock.settimeout(None)

            op, letter_byte = hdr[0], hdr[1:2]

            if op != OP_GUESS:
                logging.warning(f"Operação inesperada {op} do GUESSER, esperando OP_GUESS.")
                raise ConnectionError("Protocolo inesperado do GUESSER durante palpite")

            ch = letter_byte.decode('ascii').lower()
            logging.debug(f"Palpite '{ch}' recebido do GUESSER.")

            if not ch.isalpha() or len(ch) != 1 or ch in guessed_letters_set:
                logging.debug("Letra inválida, não é letra, ou repetida; ignorando.")
                send_game_state(guesser_sock, setter_sock, hidden_word_list, wrong_guesses_set, MAX_ERRORS - errors, True)
                continue

            guessed_letters_set.add(ch)

            if ch in word:
                positions = [i for i, c in enumerate(word) if c == ch]
                for i in positions:
                    hidden_word_list[i] = ch
                logging.debug(f"Acerto da letra '{ch}' em posições {positions}")
            else:
                errors += 1
                wrong_guesses_set.add(ch)
                logging.debug(f"Erro #{errors} com a letra '{ch}'")

            # Verifica condição de fim de jogo antes de pedir próximo input
            won = "_" not in hidden_word_list
            if won:
                logging.info(f"GUESSER ({players_data[guesser_sock]['id']}) VENCEU o turno! Palavra: {word}")
                sendall_safe(guesser_sock, bytes([OP_GAME_OVER_WIN, len(word)]) + word.encode('ascii'))
                sendall_safe(setter_sock, bytes([OP_OPPONENT_WON, len(word)]) + word.encode('ascii'))
                players_data[guesser_sock]['score'] += 1
                break
            elif errors >= MAX_ERRORS:
                logging.info(f"GUESSER ({players_data[guesser_sock]['id']}) PERDEU o turno! Max erros atingido. Palavra: {word}")
                sendall_safe(guesser_sock, bytes([OP_GAME_OVER_LOSE, len(word)]) + word.encode('ascii'))
                sendall_safe(setter_sock, bytes([OP_OPPONENT_LOST, len(word)]) + word.encode('ascii'))
                break
            else:
                send_game_state(guesser_sock, setter_sock, hidden_word_list, wrong_guesses_set, MAX_ERRORS - errors, True)

        return True

    except (ConnectionError, socket.timeout) as e:
        logging.error(f"Erro de conexão/timeout durante a rodada: {e}. Player {players_data.get(guesser_sock, {}).get('id', 'N/A')} ou {players_data.get(setter_sock, {}).get('id', 'N/A')} desconectou/travou.")
        return False
    except Exception as e:
        logging.exception(f"Erro inesperado durante a rodada: {e}.")
        return False

def handle_game_session(client_sockets):
    """
    Gerencia a sessão completa de jogo entre dois clientes, incluindo múltiplos reinícios.
    Retorna uma lista de sockets que desejam continuar e devem ser adicionados ao lobby.
    """
    p1_sock, p2_sock = client_sockets
    players_data = {
        p1_sock: {"id": 1, "score": 0},
        p2_sock: {"id": 2, "score": 0}
    }

    current_players = [p1_sock, p2_sock] # Cópia mutável para alternar papéis

    while True:

        if random.random() < 0.5: # Alterna aleatoriamente para cada nova rodada
            setter_sock, guesser_sock = current_players[0], current_players[1]
        else:
            setter_sock, guesser_sock = current_players[1], current_players[0]

        logging.info(f"Iniciando rodada: Player {players_data[setter_sock]['id']} (SETTER), Player {players_data[guesser_sock]['id']} (GUESSER).")

        round_ok = play_round(setter_sock, guesser_sock, players_data)

        if not round_ok:
            logging.info("Rodada encerrada devido a erro. Retornando sockets restantes para o lobby.")
            for sock in client_sockets:
                if sock.fileno() != -1:
                    try:
                        sock.close()
                    except:
                        pass
            return []

        logging.info(">> Enviando OP_RESTART a ambos para decisão de nova partida.")

        restart_decisions = {}


        sockets_to_poll = list(client_sockets)

        for sock in client_sockets:
            sendall_safe(sock, bytes([OP_RESTART, 1]))

        for sock in client_sockets:
            try:
                sock.settimeout(TIMEOUT)
                hdr = recv_exact(sock, 2)
                sock.settimeout(None)
                op_restart_resp, flag = hdr[0], hdr[1]
                if op_restart_resp == OP_RESTART:
                    restart_decisions[sock] = (flag == 1)
                    logging.info(f"Player{players_data[sock]['id']} escolheu {'continuar' if flag else 'sair'}")
                else:
                    logging.warning(f"Opcode inesperado {op_restart_resp} durante RESTART de Player{players_data[sock]['id']}. Assumindo 'sair'.")
                    restart_decisions[sock] = False
            except (ConnectionError, socket.timeout):
                logging.warning(f"Conexão do Player{players_data[sock]['id']} caiu ou não respondeu durante RESTART. Assumindo 'sair'.")
                restart_decisions[sock] = False
            except Exception as e:
                logging.exception(f"Erro inesperado ao receber RESTART de Player{players_data[sock]['id']}: {e}. Assumindo 'sair'.")
                restart_decisions[sock] = False

        p1_restart = restart_decisions.get(client_sockets[0], False)
        p2_restart = restart_decisions.get(client_sockets[1], False)

        sockets_to_return = []

        if p1_restart and p2_restart:
            logging.info("Ambos os jogadores querem reiniciar. Enviando confirmação.")
            sendall_safe(client_sockets[0], bytes([OP_RESTART_CONFIRM, 1]))
            sendall_safe(client_sockets[1], bytes([OP_RESTART_CONFIRM, 1]))
            sockets_to_return.extend(client_sockets) # Ambos voltam para uma nova rodada
        else:
            if p1_restart: # p1 quer continuar, p2 não
                logging.info(f"Player{players_data[client_sockets[0]]['id']} quer continuar, Player{players_data[client_sockets[1]]['id']} não. Adicionando P1 ao lobby.")
                sendall_safe(client_sockets[0], bytes([OP_RESTART_CONFIRM, 1])) # Confirma que P1 vai para o lobby
                sendall_safe(client_sockets[1], bytes([OP_RESTART_CONFIRM, 0])) # Informa P2 que vai encerrar
                try: client_sockets[1].close() # Fecha o socket do P2
                except: pass
                sockets_to_return.append(client_sockets[0]) # Apenas P1 volta
            elif p2_restart: # p2 quer continuar, p1 não
                logging.info(f"Player{players_data[client_sockets[1]]['id']} quer continuar, Player{players_data[client_sockets[0]]['id']} não. Adicionando P2 ao lobby.")
                sendall_safe(client_sockets[1], bytes([OP_RESTART_CONFIRM, 1])) # Confirma que P2 vai para o lobby
                sendall_safe(client_sockets[0], bytes([OP_RESTART_CONFIRM, 0])) # Informa P1 que vai encerrar
                try: client_sockets[0].close() # Fecha o socket do P1
                except: pass
                sockets_to_return.append(client_sockets[1]) # Apenas P2 volta
            else: # Ambos não querem reiniciar
                logging.info("Ambos os jogadores não querem reiniciar. Encerrando conexões.")
                sendall_safe(client_sockets[0], bytes([OP_RESTART_CONFIRM, 0]))
                sendall_safe(client_sockets[1], bytes([OP_RESTART_CONFIRM, 0]))
                try: client_sockets[0].close()
                except: pass
                try: client_sockets[1].close()
                except: pass

            # Se um ou ambos não quiserem, a sessão atual termina.
            return sockets_to_return


    return sockets_to_return

def handle_client_thread(client_sock, client_addr):
    global waiting_clients
    global waiting_clients_lock

    logging.info(f"Cliente {client_addr} conectado, adicionado ao lobby.")

    # Adiciona o cliente à lista de espera e informa que está aguardando
    with waiting_clients_lock:
        waiting_clients.append(client_sock)
    sendall_safe(client_sock, bytes([OP_WAITING_FOR_PLAYER, 0]))

    # Loop para tentar formar pares ou ser pareado
    while True:
        paired_clients = []
        with waiting_clients_lock:
            # Tenta encontrar um par para o cliente atual
            # Remove o cliente atual da lista temporariamente para não pareá-lo consigo mesmo
            if client_sock in waiting_clients and len(waiting_clients) >= 2:
                temp_waiting_clients = [s for s in waiting_clients if s != client_sock]
                if temp_waiting_clients: # Se há pelo menos mais um cliente esperando
                    paired_clients = [client_sock, temp_waiting_clients[0]]
                    # Remove os clientes pareados da lista global
                    waiting_clients.remove(client_sock)
                    waiting_clients.remove(temp_waiting_clients[0])
            elif client_sock.fileno() == -1: # Se o próprio socket foi fechado por outra thread
                logging.info(f"Cliente {client_addr} foi fechado por outra thread, encerrando thread do cliente.")
                break # Sai do loop da thread do cliente

        if len(paired_clients) == 2:
            logging.info(f"Formado par com {paired_clients[0].getpeername()} e {paired_clients[1].getpeername()}. Iniciando sessão de jogo.")
            try:
                # A thread que chamou handle_game_session assume a responsabilidade pelos sockets
                remaining_sockets = handle_game_session(paired_clients)

                with waiting_clients_lock:
                    for s in remaining_sockets:
                        if s.fileno() != -1:
                            waiting_clients.append(s)
                            sendall_safe(s, bytes([OP_WAITING_FOR_PLAYER, 0]))
                            logging.info(f"Cliente {s.getpeername()} voltou para o lobby.")

            except Exception as e:
                logging.exception(f"Erro ao gerenciar sessão de jogo: {e}")
                for s in paired_clients:
                    try:
                        s.close()
                    except:
                        pass
            break # A thread do cliente atual encerra após tentar formar um par
        else:
            time.sleep(1)
    if client_sock.fileno() != -1:
        with waiting_clients_lock:
            if client_sock not in waiting_clients: # Se ele não voltou para o lobby (encerrou)
                try:
                    client_sock.close()
                    logging.info(f"Cliente {client_addr} desconectado (thread finalizada).")
                except Exception as e:
                    logging.warning(f"Erro ao fechar socket final para {client_addr}: {e}")


waiting_clients = []
waiting_clients_lock = threading.Lock()

def main():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind((HOST, PORT))
    srv.listen(5) # Pode ouvir mais de 2, para o "lobby"
    logging.info(f"Servidor em {HOST}:{PORT}, aguardando pares...")


    while True:
        try:
            conn, addr = srv.accept()
            client_thread = threading.Thread(target=handle_client_thread, args=(conn, addr))
            client_thread.daemon = True # Permite que o programa principal saia mesmo com threads ativas
            client_thread.start()
        except KeyboardInterrupt:
            logging.info("Servidor encerrado pelo usuário.")
            break
        except Exception as e:
            logging.error(f"Erro ao aceitar nova conexão: {e}")

    srv.close()
    logging.info("Servidor finalizado.")

if __name__ == '__main__':
    main()