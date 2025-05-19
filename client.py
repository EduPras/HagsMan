import socket
import logging
import struct

# Configuração de logs
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(levelname)s %(message)s',
    datefmt='%H:%M:%S'
)

HOST = 'localhost'
PORT = 12345

OP_SETWORD = 1
OP_GUESS   = 2
OP_UPDATE  = 3
OP_RESTART = 4
OP_START   = 5  # novo


def recv_exact(sock, n):
    buf = b''
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Conexão encerrada pelo servidor")
        buf += chunk
    logging.debug(f"Recebido {buf!r}")
    return buf


def main():
    s = socket.socket()
    s.connect((HOST, PORT))
    logging.info("Conectado ao servidor.")

    try:
        while True:
            logging.debug("Esperando opcode do servidor...")
            op = recv_exact(s, 1)[0]
            logging.debug(f"Opcode {op} recebido")

            if op == OP_SETWORD:
                word = input("🔒 Palavra secreta: ").strip().lower()
                s.sendall(word.encode('ascii'))
                logging.debug(f"Enviou palavra '{word}'")

            elif op == OP_START:
                length = recv_exact(s,1)[0]
                print(f"🔍 Comece a adivinhar! Palavra tem {length} letras.")
                logging.debug(f"OP_START: length={length}")

                # Entrada de letra como guesser
                guess = input("Letra: ").strip().lower()[:1]
                s.sendall(bytes([OP_GUESS]) + guess.encode('ascii'))
                logging.debug(f"Enviou palpite inicial '{guess}'")

            elif op == OP_UPDATE:
                letter = recv_exact(s,1).decode('ascii')
                flag = recv_exact(s,1)[0]
                logging.debug(f"OP_UPDATE recebido: letter={letter}, flag={flag}")
                if flag == 1:
                    cnt = recv_exact(s,1)[0]
                    pos = list(recv_exact(s,cnt))
                    print(f"[+] Letra '{letter}' acertou nas posições {pos}")
                    logging.debug(f"Detalhes acerto: posições {pos}")
                else:
                    print(f"[-] Letra '{letter}' não está na palavra.")
                    logging.debug("Detalhes erro: flag=0")

                # Permitir próxima tentativa
                guess = input("Próxima letra: ").strip().lower()[:1]
                s.sendall(bytes([OP_GUESS]) + guess.encode('ascii'))
                logging.debug(f"Enviou nova tentativa '{guess}'")

            elif op == OP_RESTART:
                ans = input("🔄 Jogar de novo? (1=sim / 0=não): ").strip()
                flag = 1 if ans == '1' else 0
                s.sendall(bytes([OP_RESTART, flag]))
                logging.debug(f"Respondeu restart={flag}")
                if flag == 0:
                    break

            elif op == OP_GUESS:
                guess = input("Letra: ").strip().lower()[:1]
                s.sendall(bytes([OP_GUESS]) + guess.encode('ascii'))
                logging.debug(f"Enviou palpite via OP_GUESS '{guess}'")

            else:
                logging.warning(f"Opcode desconhecido: {op}")

    except ConnectionError as e:
        logging.error(f"Conexão caiu: {e}")
    finally:
        s.close()
        logging.info("Cliente encerrado.")

if __name__ == '__main__':
    main()