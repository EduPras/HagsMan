import socket
import threading
import struct
import time
import logging

# Configuração do logger
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(levelname)s %(message)s',
    datefmt='%H:%M:%S'
)

HOST = '0.0.0.0'
PORT = 12345

# Op‑codes
OP_SETWORD = 1
OP_GUESS   = 2
OP_UPDATE  = 3
OP_RESTART = 4
OP_START   = 5  # novo

MAX_ERRORS = 6
TIMEOUT    = 60  # segundos

def sendall(sock, data: bytes):
    try:
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

def handle_pair(client_sockets):
    p1, p2 = client_sockets
    players = [p1, p2]
    scores = [0, 0]
    logging.info("=== Iniciando nova partida entre dois jogadores ===")

    # Dois turnos (cada um escolhe palavra uma vez)
    for turn in range(2):
        setter = turn % 2
        guesser = (turn + 1) % 2
        s_set, s_guess = players[setter], players[guesser]

        logging.info(f"Turno {turn+1}: setter=Player{setter+1}, guesser=Player{guesser+1}")

        # 1) OPCODE 1: solicitar palavra
        sendall(s_set, bytes([OP_SETWORD]))
        logging.debug(">> OP_SETWORD enviado.")
        word = s_set.recv(1024).decode('ascii').strip().lower()
        logging.debug(f"Player{setter+1} escolheu: '{word}'")
        word_len = len(word)

        # 1.5) OPCODE 5: avisar guesser que pode iniciar e tamanho
        sendall(s_guess, bytes([OP_START, word_len]))
        logging.debug(f">> OP_START enviado ao guesser com length={word_len}")

        hidden = ['_' if c.isalpha() else c for c in word]
        guessed = set()
        errors = 0
        start = time.time()

        # 2) loop de tentativas
        while '_' in hidden and (time.time() - start) < TIMEOUT and errors < MAX_ERRORS:
            hdr = recv_exact(s_guess, 2)
            op, letter = hdr[0], hdr[1:2]
            if op != OP_GUESS:
                logging.warning(f"Operação inesperada {op}")
                break

            ch = letter.decode('ascii').lower()
            logging.debug(f"Guess '{ch}' recebido")

            if ch in guessed or not ch.isalpha():
                logging.debug("Letra inválida ou repetida; ignorando")
                continue

            guessed.add(ch)
            if ch in word:
                positions = [i for i, c in enumerate(word) if c == ch]
                for i in positions:
                    hidden[i] = ch
                resp_g = bytes([1, len(positions)]) + bytes(positions)
                resp_s = bytes([OP_UPDATE]) + letter + resp_g
                logging.debug(f"Acerto em {positions}")
            else:
                errors += 1
                resp_g = bytes([0])
                resp_s = bytes([OP_UPDATE]) + letter + resp_g
                logging.debug(f"Erro #{errors}")

            sendall(s_guess, resp_s)
            sendall(s_set,   resp_s)
            logging.debug(f"Estado oculto: {''.join(hidden)}")

        # finalize turno
        won = '_' not in hidden
        time_spent = int(time.time() - start)
        logging.info(f"Turno {turn+1} {'VENCEU' if won else 'PERDEU'} em {time_spent}s e {errors} erros")
        if won:
            pts = max(0, 100 - errors*10 - time_spent)
            scores[guesser] += pts
            logging.info(f"Player{guesser+1} +{pts}pts (total {scores[guesser]})")

    # 3) OP_RESTART
    logging.info(">> Enviando OP_RESTART a ambos")
    for s in players:
        sendall(s, bytes([OP_RESTART]))
    flags = []
    for idx, s in enumerate(players):
        hdr = recv_exact(s, 2)
        flag = 1 if hdr[1] == 1 else 0
        flags.append(flag)
        logging.info(f"Player{idx+1} escolheu {'continuar' if flag else 'sair'}")

    # envia placar final
    for idx, s in enumerate(players):
        msg = bytes([OP_UPDATE, 0]) + struct.pack('!I', scores[idx])
        sendall(s, msg)
        logging.debug(f"Placar final {scores[idx]} enviado a Player{idx+1}")
        s.close()

    if flags == [1,1]:
        logging.info("Reiniciando entre mesmos jogadores")
        return True
    elif flags == [0,0]:
        logging.info("Encerrando servidor")
        return False
    else:
        logging.info("Decisões mistas → volta ao estado 0")
        raise RuntimeError("Um quis, outro não")

def main():
    srv = socket.socket()
    srv.bind((HOST, PORT))
    srv.listen(2)
    logging.info(f"Servidor em {HOST}:{PORT}, aguardando pares...")

    while True:
        clients = []
        for i in (1,2):
            conn, addr = srv.accept()
            logging.info(f"Player{i} conectado: {addr}")
            clients.append(conn)

        try:
            cont = handle_pair(clients)
        except RuntimeError:
            continue
        if not cont:
            break

    srv.close()
    logging.info("Servidor finalizado.")

if __name__ == '__main__':
    main()
