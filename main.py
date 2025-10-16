from pathlib import Path
import sys
import os

# Ensure project root is on sys.path when run directly
sys.path.append(os.path.dirname(__file__))

from macros import data, pets, consumables, equipment, shapeshift

def define_env(env):
    docs_dir = Path(env.conf["docs_dir"])

    # Load all YAML once; expose as variables
    store = data.load_all(docs_dir)
    env.variables.update(store)  # pets, consumables, equipment, shapeshift, shapeshift_bonuses

    # Register feature areas (they add variables & macros to env)
    pets.register(env, store)          # {{ pet_row(...) }}
    consumables.register(env, store)   # {{ consumables_table(...) }}
    equipment.register(env, store)     # {{ gear_index(...) }}, etc.
    shapeshift.register(env, store)    # {{ shapeshift_table(...) }}, etc.
