import os

def print_tree(path, prefix=""):
    # Liste le contenu trié (dossiers puis fichiers)
    items = sorted(os.listdir(path))
    for index, item in enumerate(items):
        full_path = os.path.join(path, item)
        is_last = index == len(items) - 1

        # Choix du préfixe graphique
        connector = "└── " if is_last else "├── "

        print(prefix + connector + item)

        # Si c'est un dossier -> récursion
        if os.path.isdir(full_path):
            new_prefix = prefix + ("    " if is_last else "│   ")
            print_tree(full_path, new_prefix)


if __name__ == "__main__":
    start_path = os.getcwd()  # dossier actuel
    print(os.path.basename(start_path) or start_path)
    print_tree(start_path)
