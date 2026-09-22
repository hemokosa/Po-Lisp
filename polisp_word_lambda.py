#!/usr/bin/env python3
"""Po-Lisp 語の版 + lambda / label — 名前と再帰のある対話環境.

7つの公理  5つの基本関数  atom  eq  car  cdr  cons
           2つの特殊形式  quote  cond
に、さらにふたつの特殊形式を足したもの。

    (lambda (仮引数...) 本体)   名前のない関数をつくる
    (label 名 式)               その式の中から自分自身を名前で呼べるようにする

Po-Lisp 語の版の段階的な実装の第二段。第一段（7公理だけ）は polisp_word.py。

使い方:
    python3 polisp_word_lambda.py             対話モード
    python3 polisp_word_lambda.py examples/polisp_word/uta.lisp
"""

import sys

sys.setrecursionlimit(10000)

# ---------------------------------------------------------------- データ表現
#   アトム   -> str（記号）、Closure、Primitive
#   リスト   -> tuple。空リスト NIL は ()
NIL = ()
T = "t"


def is_symbol(x):
    return isinstance(x, str)


def is_list(x):
    return isinstance(x, tuple)


def truthy(x):
    """() だけが偽。それ以外はすべて真。"""
    return x != NIL


class LispError(Exception):
    pass


class Incomplete(LispError):
    """括弧が閉じていない。対話モードでは次の行を待つ合図になる。"""


class Closure:
    """lambda がつくる値。仮引数と本体と、生まれた場所の環境を抱えている。"""

    __slots__ = ("params", "body", "env", "name")

    def __init__(self, params, body, env, name=None):
        self.params, self.body, self.env, self.name = params, body, env, name


class Primitive:
    """基本関数を値にしたもの。関数に渡したり返したりできる。"""

    __slots__ = ("name", "fn", "arity")

    def __init__(self, name, fn, arity):
        self.name, self.fn, self.arity = name, fn, arity


class Def:
    """:def 名 式 — 環境に名前を登録する、言語ではなくセッションの機能。"""

    __slots__ = ("name", "expr")

    def __init__(self, name, expr):
        self.name, self.expr = name, expr


def is_atom(x):
    return is_symbol(x) or x == NIL or isinstance(x, (Closure, Primitive))


# ---------------------------------------------------------------------- 環境
class Env:
    """名前から値への対応表。親をたどって外側の環境を探しにいく。"""

    __slots__ = ("vars", "parent")

    def __init__(self, vars=None, parent=None):
        self.vars = vars if vars is not None else {}
        self.parent = parent

    def lookup(self, name):
        env = self
        while env is not None:
            if name in env.vars:
                return env.vars[name]
            env = env.parent
        raise LispError(
            "%s には値がありません。データとして使うなら '%s と書きます" % (name, name)
        )

    def define(self, name, value):
        self.vars[name] = value


# -------------------------------------------------------------------- 読み込み
DELIMS = "()';"


def tokenize(src):
    tokens, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c == ";":
            while i < n and src[i] != "\n":
                i += 1
        elif c.isspace():
            i += 1
        elif c in "()'":
            tokens.append(c)
            i += 1
        else:
            j = i
            while j < n and not src[j].isspace() and src[j] not in DELIMS:
                j += 1
            tokens.append(src[i:j])
            i = j
    return tokens


def parse(tokens, pos=0):
    """tokens[pos] から式をひとつ読む -> (式, 次の位置)"""
    if pos >= len(tokens):
        raise Incomplete("式が途中で終わっています")
    tok = tokens[pos]
    if tok == "(":
        items, pos = [], pos + 1
        while True:
            if pos >= len(tokens):
                raise Incomplete("閉じ括弧がありません")
            if tokens[pos] == ")":
                return tuple(items), pos + 1
            item, pos = parse(tokens, pos)
            items.append(item)
    if tok == ")":
        raise LispError("対応する開き括弧のない ) があります")
    if tok == "'":
        quoted, pos = parse(tokens, pos + 1)
        return ("quote", quoted), pos
    return tok, pos + 1


def parse_top(tokens, pos=0):
    """トップレベルの項目をひとつ読む。:def なら Def を返す。"""
    if pos < len(tokens) and tokens[pos] == ":def":
        if pos + 1 >= len(tokens):
            raise Incomplete(":def のあとに名前が要ります")
        name = tokens[pos + 1]
        if name in ("(", ")", "'"):
            raise LispError(":def のあとには名前を書きます")
        expr, pos = parse(tokens, pos + 2)
        return Def(name, expr), pos
    return parse(tokens, pos)


def read_one(src):
    tokens = tokenize(src)
    if not tokens:
        return None
    item, pos = parse_top(tokens)
    if pos != len(tokens):
        raise LispError("1行に式がふたつ以上あります")
    return item


def read_all(src):
    tokens, pos, items = tokenize(src), 0, []
    while pos < len(tokens):
        item, pos = parse_top(tokens, pos)
        items.append(item)
    return items


# -------------------------------------------------------------------- 書き出し
def write(x):
    if is_symbol(x):
        return x
    if isinstance(x, Closure):
        params = " ".join(x.params)
        if x.name:
            return "#<lambda %s (%s)>" % (x.name, params)
        return "#<lambda (%s)>" % params
    if isinstance(x, Primitive):
        return "#<公理 %s>" % x.name
    return "(" + " ".join(write(e) for e in x) + ")"


# ---------------------------------------------------------------------- 評価器
SPECIAL = ("quote", "cond", "lambda", "label")


def seval(x, env):
    while True:                       # 末尾位置はループで回す（末尾呼び出しの最適化）
        if is_symbol(x):
            return env.lookup(x)
        if not is_list(x):            # Closure / Primitive は自分自身に評価される
            return x
        if x == NIL:
            return NIL

        op, args = x[0], x[1:]

        if is_symbol(op) and op in SPECIAL:
            if op == "quote":
                need(op, args, 1)
                return args[0]

            if op == "lambda":
                need(op, args, 2)
                return Closure(check_params(args[0]), args[1], env)

            if op == "label":
                need(op, args, 2)
                if not is_symbol(args[0]):
                    raise LispError("label の第1引数は名前です: %s" % write(args[0]))
                inner = Env({}, env)          # 自分の名前が見える環境をつくり
                val = seval(args[1], inner)   # そこで中身を評価して
                if isinstance(val, Closure) and val.name is None:
                    val.name = args[0]
                inner.define(args[0], val)    # あとから自分自身を結びつける
                return val

            if op == "cond":
                chosen = None
                for clause in args:
                    if not is_list(clause) or len(clause) != 2:
                        raise LispError(
                            "cond の節は (条件 結果) の形にします: %s" % write(clause)
                        )
                    if truthy(seval(clause[0], env)):
                        chosen = clause[1]
                        break
                if chosen is None:
                    raise LispError("cond: 真になる条件がひとつもありませんでした")
                x = chosen                    # 末尾位置なのでループの先頭へ戻る
                continue

        fn = seval(op, env)
        vals = [seval(a, env) for a in args]

        if isinstance(fn, Primitive):
            if len(vals) != fn.arity:
                raise LispError(
                    "%s は引数を%d個とります（%d個ありました）"
                    % (fn.name, fn.arity, len(vals))
                )
            return fn.fn(*vals)

        if isinstance(fn, Closure):
            if len(vals) != len(fn.params):
                raise LispError(
                    "%s は引数を%d個とります（%d個ありました）"
                    % (write(fn), len(fn.params), len(vals))
                )
            env = Env(dict(zip(fn.params, vals)), fn.env)
            x = fn.body                       # 末尾呼び出し: 積まずに置き換える
            continue

        raise LispError("%s は関数ではありません" % write(fn))


def need(op, args, n):
    if len(args) != n:
        raise LispError("%s は引数を%d個とります（%d個ありました）" % (op, n, len(args)))


def check_params(params):
    if not is_list(params):
        raise LispError("lambda の仮引数はリストで書きます: %s" % write(params))
    for p in params:
        if not is_symbol(p):
            raise LispError("仮引数は名前でなければなりません: %s" % write(p))
    if len(set(params)) != len(params):
        raise LispError("仮引数の名前が重なっています: %s" % write(params))
    return params


# -------------------------------------------------------------------- 公理の実装
def prim_atom(x):
    return T if is_atom(x) else NIL


def prim_eq(a, b):
    for v in (a, b):
        if not is_atom(v):
            raise LispError("eq が比べられるのはアトムだけです: %s" % write(v))
    if is_symbol(a) and is_symbol(b):
        return T if a == b else NIL
    return T if a is b or (a == NIL and b == NIL) else NIL


def prim_car(xs):
    if not is_list(xs) or xs == NIL:
        raise LispError("car: 空でないリストが必要です: %s" % write(xs))
    return xs[0]


def prim_cdr(xs):
    if not is_list(xs) or xs == NIL:
        raise LispError("cdr: 空でないリストが必要です: %s" % write(xs))
    return xs[1:]


def prim_cons(x, xs):
    if not is_list(xs):
        raise LispError("cons の第2引数はリストでなければなりません: %s" % write(xs))
    return (x,) + xs


def global_env():
    env = Env()
    for name, fn, arity in (
        ("atom", prim_atom, 1),
        ("eq", prim_eq, 2),
        ("car", prim_car, 1),
        ("cdr", prim_cdr, 1),
        ("cons", prim_cons, 2),
    ):
        env.define(name, Primitive(name, fn, arity))
    env.define(T, T)
    env.define("nil", NIL)
    return env


BUILTIN_NAMES = frozenset(("atom", "eq", "car", "cdr", "cons", T, "nil"))


# ------------------------------------------------------------------------ REPL
HELP = """\
7つの公理 = 5つの基本関数 + 2つの特殊形式

5つの基本関数（引数を評価してから働く。値なので渡すこともできる）:
  (atom x)          x がアトム（記号・()・関数）なら t、リストなら ()
  (eq x y)          ふたつのアトムが同じなら t、ちがえば ()
  (car xs)          リストの先頭
  (cdr xs)          リストの先頭を除いた残り
  (cons x xs)       x を先頭に足した新しいリスト

2つの特殊形式（引数を評価しない）:
  (quote x)  'x     x を評価せずそのまま返す
  (cond (p e) ...)  p を順に試し、最初に真になった節の e を返す

さらにふたつの特殊形式:
  (lambda (x y) 本体)   名前のない関数。値なので、渡すことも返すこともできる
  (label 名 式)         式の中から自分自身を名前で呼べる ── 再帰はここから生まれる

真偽:  () が偽。それ以外はすべて真。t と nil は自分自身に評価される。

例:
  ((lambda (x) (cons x (cons x '()))) '木)      -> (木 木)
  (label 数 (lambda (xs)
    (cond ((atom xs) '())
          (t (cons '一 (数 (cdr xs)))))))       ; 再帰する関数
  ((label ap (lambda (xs ys)
     (cond ((atom xs) ys)
           (t (cons (car xs) (ap (cdr xs) ys))))))
   '(雪 が) '(降る))                            -> (雪 が 降る)

コマンド:
  :def 名 式        名前に値を覚えさせる（言語ではなくセッションの機能）
  :env              覚えている名前の一覧
  :help  :quit  :load ファイル名
複数行にまたがる式は、括弧が閉じるまで入力を続けられます（.. が出ます）。
"""


def run_item(item, env):
    """Def なら登録して名前を、式なら評価して値を返す。"""
    if isinstance(item, Def):
        env.define(item.name, seval(item.expr, env))
        return item.name
    return seval(item, env)


def run_source(src, env, show=False):
    for item in read_all(src):
        try:
            val = run_item(item, env)
        except LispError as e:
            print("error: %s" % e, file=sys.stderr)
            continue
        except RecursionError:
            print("error: 再帰が深すぎます", file=sys.stderr)
            continue
        if show:
            print(val if isinstance(item, Def) else write(val))


def repl():
    env = global_env()
    try:
        import atexit
        import os
        import readline                       # 行編集と履歴

        histfile = os.path.expanduser("~/.polisp_word_history")
        try:
            readline.read_history_file(histfile)
        except OSError:
            pass
        atexit.register(lambda: _save_history(readline, histfile))
    except ImportError:
        pass

    print("Po-Lisp 語の版 + lambda / label — :help で説明、:quit で終了。")
    buf = ""
    while True:
        try:
            line = input(".. " if buf else "> ")
        except EOFError:
            print()
            return
        except KeyboardInterrupt:
            print("^C")
            buf = ""
            continue

        if not buf:
            cmd = line.strip()
            if cmd in (":quit", ":q"):
                return
            if cmd in (":help", ":h", "?"):
                print(HELP, end="")
                continue
            if cmd == ":env":
                names = [n for n in env.vars if n not in BUILTIN_NAMES]
                print(" ".join(names) if names else "（まだ何も覚えていません）")
                continue
            if cmd.startswith(":load "):
                path = cmd[len(":load "):].strip()
                try:
                    with open(path, encoding="utf-8") as f:
                        run_source(f.read(), env, show=True)
                except OSError as e:
                    print("error: %s" % e, file=sys.stderr)
                except LispError as e:
                    print("error: %s" % e, file=sys.stderr)
                continue

        buf = buf + "\n" + line if buf else line
        if not buf.strip():
            buf = ""
            continue

        try:
            item = read_one(buf)
        except Incomplete:
            continue                          # 括弧が閉じるまで待つ
        except LispError as e:
            print("error: %s" % e, file=sys.stderr)
            buf = ""
            continue
        buf = ""

        if item is None:
            continue
        try:
            val = run_item(item, env)
        except LispError as e:
            print("error: %s" % e, file=sys.stderr)
            continue
        except RecursionError:
            print("error: 再帰が深すぎます", file=sys.stderr)
            continue
        print(val if isinstance(item, Def) else write(val))


def _save_history(readline, histfile):
    try:
        readline.write_history_file(histfile)
    except OSError:
        pass


def main(argv):
    if len(argv) > 1:
        with open(argv[1], encoding="utf-8") as f:
            run_source(f.read(), global_env(), show=True)
    elif sys.stdin.isatty():
        repl()
    else:
        run_source(sys.stdin.read(), global_env(), show=True)


if __name__ == "__main__":
    main(sys.argv)
