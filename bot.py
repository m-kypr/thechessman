import math
import win32gui
import cv2
from PIL import Image, ImageGrab, ImageChops
from os import path, mkdir, listdir
from pynput.mouse import Button, Controller

BASE_PATH = path.dirname(path.abspath(__file__))
PIECES_PATH = path.join(BASE_PATH, 'pcs')
if not path.isdir(PIECES_PATH):
    mkdir(PIECES_PATH)
print(BASE_PATH)

p1 = (614, 202)
p2 = (1358, 946)

p1 = (620, 176)
p2 = (1364, 920)

dim = ((p2[0] - p1[0]) / 8, (p2[1] - p1[1]) / 8)
print(dim)

col1 = (240, 217, 181)
col1sel = (205, 210, 107)
col2 = (181, 136, 99)
col2sel = (171, 162, 59)


def unblend(c1, c1blend, c2, c2blend, p=1, q=100, n=100, depth=0):
    """Extract the color of which both c1 and c2 got blended. 

    This algorithm approximates the color by comparing the differnce between the two reverse color addition results and adjusting the iteration
    """

    def extract_green(c, cblend, t=0.5):
        g = [0, 0, 0]
        for i in range(3):
            g[i] = abs(t**-.5 * (cblend[i] - c[i] * (1 - t)**.5))
        return g
    m = {}
    for i in range(p, q):
        t = i / n
        a = extract_green(c1, c1blend, t)
        b = extract_green(c2, c2blend, t)
        s = 0
        for j in range(3):
            # maybe use mean squared error or some other bs
            s += abs(a[j] - b[j])
        m[i] = s
    idx = min(m, key=m.get)
    if idx / n == 0 or depth > 100:
        return [int(round(x, 0)) for x in a], idx / n
    return unblend(c1, c1blend, c2, c2blend, (idx - 1) * 10, (idx + 1) * 10, n * 10, depth + 1)


color, blend_value = unblend(col1, col1sel, col2, col2sel)

print(
    f'Original color: {color}, blend factor: {blend_value}, alpha: {int(blend_value * 256)}')
quit()


class Board:
    """
    12 States Piece: r, n, b, k, q, p, black or white
    -> 4 bits per square => 256 bits for board
    2 States Turn: b or w
    3 States Winner: b, w, no one
    -> 3 bit
    => 259 Bits for board
    """

    def __init__(self):
        self.board = [[0, 0, 0, 0, 0, 0, 0, 0],
                      [0, 0, 0, 0, 0, 0, 0, 0],
                      [0, 0, 0, 0, 0, 0, 0, 0],
                      [0, 0, 0, 0, 0, 0, 0, 0],
                      [0, 0, 0, 0, 0, 0, 0, 0],
                      [0, 0, 0, 0, 0, 0, 0, 0],
                      [0, 0, 0, 0, 0, 0, 0, 0],
                      [0, 0, 0, 0, 0, 0, 0, 0]]
        self.turn = 0
        self.winner = 0


def screen(url):
    toplist, winlist = [], []

    def enum_cb(hwnd, results):
        winlist.append((hwnd, win32gui.GetWindowText(hwnd)))

    win32gui.EnumWindows(enum_cb, toplist)

    browser = [(hwnd, title)
               for hwnd, title in winlist if url in title.lower()]
    browser = browser[0]
    hwnd = browser[0]

    win32gui.SetForegroundWindow(hwnd)
    bbox = win32gui.GetWindowRect(hwnd)
    img = ImageGrab.grab(bbox)
    return img


def parse_screen(img, start_image):
    img = img.convert('RGBA')
    r, g, b, a = img.getpixel((p1[0] + 1, p1[1] + 1))
    col1 = (r, g, b, a)
    r, g, b, a = img.getpixel((p1[0] + dim[0], p1[1]))
    col2 = (r, g, b, a)

    print(col1, col2)

    def _read_pieces(image, jr, ir, flatten=False):
        tiles = []
        for j in range(jr[1]):
            tiles.append([])
        for j in range(*jr):
            for i in range(*ir):
                x = i * dim[0] + p1[0]
                y = j * dim[1] + p1[1]
                tile = image.crop((x, y, x + dim[0], y + dim[1]))
                if ((i + j) % 2 == 0):
                    col = col1
                else:
                    col = col2
                pxls = tile.load()
                for k in range(int(dim[0])):
                    for l in range(int(dim[1])):
                        if (pxls[k, l] == col):
                            pxls[k, l] = (0, 0, 0, 0)
                tiles[j].append(tile)
        if flatten:
            return [x for y in tiles for x in y]
        return tiles

    def _generate_pieces(start_image):
        print('generating pieces pngs')
        pp = 'rnbqkp'
        jr = (0, 1)
        ir = (0, 5)
        pieces = [f'b{x}' for x in pp]
        tiles = _read_pieces(start_image, jr, ir, flatten=True)
        for i in range(len(tiles)):
            tiles[i].save(path.join(PIECES_PATH, pieces[i] + '.png'))
        jr = (7, 8)
        ir = (0, 5)
        pieces = [f'w{x}' for x in pp]
        tiles = _read_pieces(start_image, jr, ir, flatten=True)
        for i in range(len(tiles)):
            tiles[i].save(path.join(PIECES_PATH, pieces[i] + '.png'))

        _read_pieces(start_image, (1, 2), (0, 1), flatten=True)[0].save(
            path.join(PIECES_PATH, 'bp.png'))
        _read_pieces(start_image, (6, 7), (0, 1), flatten=True)[0].save(
            path.join(PIECES_PATH, 'wp.png'))

    if len(listdir(PIECES_PATH)) == 0:
        _generate_pieces(start_image)

    jr = (0, 8)
    ir = (0, 8)
    tiles = _read_pieces(img, jr, ir)

    m = {'wr': 0, 'wn': 1, 'wb': 2, 'wq': 3, 'wk': 4, 'wp': 5,
         'br': 6, 'bn': 7, 'bb': 8, 'bq': 9, 'bk': 10, 'bp': 11}
    board = Board()
    pieces = {}
    for p in listdir(PIECES_PATH):
        img = Image.open(path.join(PIECES_PATH, p))
        pieces[p[:2]] = (img, img.load())
    for i in range(len(tiles)):
        for j in range(len(tiles[i])):
            t = tiles[i][j]
            tpxls = t.load()
            cs = {}
            for p in pieces:
                cs[p] = 0
                for k in range(t.size[0]):
                    for l in range(t.size[1]):
                        if tpxls[k, l] != pieces[p][1][k, l]:
                            cs[p] += 1
            val, idx = min((val, idx) for (idx, val) in enumerate(cs.values()))
            print(i, j, cs)
            if i == 4 and j == 5:
                t.show()
            if val < 1000:  # confidence level
                p = list(cs.keys())[idx]
                board.board[i][j] = m[p]
    return board


start_img = Image.open(path.join(BASE_PATH, 'screenshot.PNG'))
img = screen('lichess.org')
img.save('a.png')
board = parse_screen(img, start_img)
print(board.board)
# mouse = Controller()

# print(f'The current pointer position is {mouse.position}')
# mouse.position = (614, 202)
# print('Now we have moved it to {0}'.format(
#     mouse.position))

# mouse.move(5, -5)

# mouse.press(Button.left)
# mouse.release(Button.left)

# mouse.click(Button.left, 2)

# mouse.scroll(0, 2)
