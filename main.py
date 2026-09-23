import argparse
from check import CheckAll, CheckPlant, CheckClient, CheckServer


def main():                                 #---------- PROBADO ----------#
    class CustomParser(argparse.ArgumentParser):
        def error(self, message):
            print(f"Error: {message}")
            print(f"Uso correcto:")
            print(f"   python main.py --plant <planta>    # Verificar por planta")
            print(f"   python main.py --server <servidor> # Verificar por servidor")
            print(f"   python main.py --client <cliente>  # Verificar por cliente (archivo YAML)")
            print(f"Ejemplos:")
            print(f"   python main.py --plant apan")
            print(f"   python main.py --plant all")
            print(f"   python main.py --server servidor1")
            print(f"   python main.py --client Api_Manzanillo")
            print(f"   python main.py --client all")
            print(f"Usa -h o --help para más información.\n")
            self.exit(2)

    parser = CustomParser(
        description='Sistema de verificación de cámaras AXIS',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument(
        '-p', '--plant',
        type=str,
        help='Nombre de la planta o "all" para todas'
    )
    group.add_argument(
        '-s', '--server',
        type=str,
        help='Nombre del servidor'
    )
    group.add_argument(
        '-c', '--client',
        type=str,
        help='Nombre del cliente (archivo YAML de conf/plants/) o "all" para todos'
    )

    args = parser.parse_args()

    if args.plant:
        plant = args.plant.upper()
        if plant == 'ALL' or plant == '':
            CheckAll()
        else:
            CheckPlant(plant, None)
    elif args.server:
        server = args.server.upper()
        CheckPlant(None, server)
    elif args.client:
        if args.client.upper() == 'ALL' or args.client == '':
            CheckAll()
        else:
            CheckClient(args.client)


if __name__ == "__main__":
    main()