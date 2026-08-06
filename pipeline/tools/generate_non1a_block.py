"""
Genera el bloque NON1A_KEYS:/NON1A: que SNANA necesita en un
SIMGEN_INCLUDE_*.INPUT para clases GENMODEL: NON1ASED.

No inventa pesos ni SNTYPE: los recibe como argumentos. Asigna peso
uniforme (1/N) a cada template listado en el NON1A.LIST de la clase
(archivo autogenerado por convert_SIMSED_to_NON1ASED.py, formato
`NON1A: <index> <name> <filename>`). MAGOFF/MAGSMEAR quedan en 0.0 --
no hay precedente de calibracion observacional para estas clases
"en desarrollo" (ver README.md, "Decisiones y correcciones").

Uso:
    python generate_non1a_block.py <ruta a NON1A.LIST> <SNTYPE>
"""
import re
import sys


def parse_non1a_list(path):
    indices = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = re.match(r"^NON1A:\s+(\d+)\s+(\S+)\s+(\S+)", line)
            if m:
                indices.append(int(m.group(1)))
    return indices


def build_block(indices, sntype):
    n = len(indices)
    wgt = 1.0 / n
    lines = [
        f"NON1A_KEYS: 5",
        f"          INDEX   WGT       MAGOFF   MAGSMEAR  SNTYPE",
    ]
    for idx in indices:
        lines.append(f"NON1A:    {idx}  {wgt:.6e}   0.0      0.0       {sntype}")
    return "\n".join(lines) + "\n"


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    list_path, sntype = sys.argv[1], sys.argv[2]
    indices = parse_non1a_list(list_path)
    if not indices:
        print(f"ERROR: no se encontraron lineas 'NON1A:' en {list_path}", file=sys.stderr)
        sys.exit(1)
    print(build_block(indices, sntype))


if __name__ == "__main__":
    main()
