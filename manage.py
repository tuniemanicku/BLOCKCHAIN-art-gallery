"""Sellart command line entry point.

    python manage.py reset          clean state: delete all chains and wallets, new admin account
    python manage.py cluster        start nodes A, B and C (each in its own window/process)
    python manage.py node A         run a single node in this terminal
    python manage.py app            open the desktop application

The independent verifier is a separate program:  python verifier/verify_chain.py --help
"""

import argparse


def ask_admin_password() -> str:
    from getpass import getpass
    from sellart.client.wallets import MIN_PASSWORD_LENGTH
    while True:
        password = getpass("New password for the 'Gallery Admin' account: ")
        if len(password) < MIN_PASSWORD_LENGTH:
            print(f"The password must have at least {MIN_PASSWORD_LENGTH} characters.")
        elif getpass("Repeat the password: ") != password:
            print("The passwords differ, try again.")
        else:
            return password


def main() -> None:
    parser = argparse.ArgumentParser(description="Sellart - art gallery ownership tickets")
    commands = parser.add_subparsers(dest="command", required=True)
    reset_parser = commands.add_parser("reset", help="reset the system to a clean state")
    reset_parser.add_argument("--admin-password", help="password of the Gallery Admin account "
                                                       "(asked interactively when omitted)")
    commands.add_parser("cluster", help="start all nodes as separate processes")
    node_parser = commands.add_parser("node", help="run one node")
    node_parser.add_argument("node_id", help="node id, e.g. A")
    commands.add_parser("app", help="open the desktop application")
    args = parser.parse_args()

    if args.command == "reset":
        from sellart.launcher import reset_environment
        reset_environment(args.admin_password or ask_admin_password())

    elif args.command == "cluster":
        from sellart.config import load_cluster_config
        from sellart.launcher import start_node_process
        for node_id in load_cluster_config().node_ids:
            start_node_process(node_id)
            print(f"node {node_id} started")

    elif args.command == "node":
        from sellart.node_server import run_node
        run_node(args.node_id.upper())

    elif args.command == "app":
        from sellart.client.ui.session_window import run_app
        run_app()


if __name__ == "__main__":
    main()
