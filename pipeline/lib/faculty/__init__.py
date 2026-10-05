from . import dgist, gist, kaist, postech, snu, unist

PARSERS = {
    "kaist": kaist.collect,
    "snu": snu.collect,
    "postech": postech.collect,
    "unist": unist.collect,
    "gist": gist.collect,
    "dgist": dgist.collect,
}
