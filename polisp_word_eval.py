#!/usr/bin/env python3
"""Po-Lisp 語の版 + lambda / label + eval — プログラムがデータになる対話環境.

7つの公理  atom  eq  car  cdr  cons  quote  cond
ふたつの形式  (lambda (仮引数...) 本体)   (label 名 式)
に、ふたつの橋を足したもの。

    (eval e a)     データを式として評価する。a は ((名前 値) ...) という連想リスト
    (apply f xs)   関数 f を、評価済みの引数リスト xs に適用する

この2つは公理ではない。公理と lambda / label だけで eval を書くことは v2 でもでき、
それは examples/polisp_word/eval.lisp にある。ここで足したのは、そうして書いた評価器と、
言語じたいの評価器を、同じ土俵で呼び比べるための橋。

Po-Lisp 語の版の段階的な実装の第三段。第一段は polisp_word.py、第二段は polisp_word_lambda.py。
同じ言語を記号で書いたものが Po-Lisp（polisp.py）。

使い方:
    python3 polisp_word_eval.py               対話モード
    python3 polisp_word_eval.py examples/polisp_word/eval.lisp
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
    """公理そのものを値にしたもの。関数に渡したり返したりできる。"""

    __slots__ = ("name", "fn", "arities", "kind")

    def __init__(self, name, fn, arities, kind="公理"):
        if isinstance(arities, int):
            arities = (arities,)
        self.name, self.fn, self.arities, self.kind = name, fn, arities, kind


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
        return "#<%s %s>" % (x.kind, x.name)
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
            if len(vals) not in fn.arities:
                raise LispError(
                    "%s は引数を%s個とります（%d個ありました）"
                    % (fn.name, "か".join(str(n) for n in fn.arities), len(vals))
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


def apply_fn(fn, vals):
    """評価済みの関数と評価済みの引数を、そのまま適用する。"""
    if isinstance(fn, Primitive):
        if len(vals) not in fn.arities:
            raise LispError(
                "%s は引数を%s個とります（%d個ありました）"
                % (fn.name, "か".join(str(n) for n in fn.arities), len(vals))
            )
        return fn.fn(*vals)
    if isinstance(fn, Closure):
        if len(vals) != len(fn.params):
            raise LispError(
                "%s は引数を%d個とります（%d個ありました）"
                % (write(fn), len(fn.params), len(vals))
            )
        return seval(fn.body, Env(dict(zip(fn.params, vals)), fn.env))
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
            raise LispError(
                "eq が比べられるのはアトムだけです: %s"
                "（リストが空かどうかを見るなら (atom x) を使います）" % write(v)
            )
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


def env_from_alist(alist, parent):
    """((名前 値) ...) という連想リストを環境にする。ドット対がないので2要素リスト。"""
    if not is_list(alist):
        raise LispError("環境は ((名前 値) ...) という連想リストです: %s" % write(alist))
    vars = {}
    for pair in reversed(alist):          # 前にあるものが勝つ
        if not is_list(pair) or len(pair) != 2 or not is_symbol(pair[0]):
            raise LispError("環境の要素は (名前 値) の形にします: %s" % write(pair))
        vars[pair[0]] = pair[1]
    return Env(vars, parent)


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

    def prim_eval(e, alist=NIL):
        """データを式として評価する。連想リストは大域環境の上に重ねる。"""
        return seval(e, env_from_alist(alist, env))

    def prim_apply(fn, args):
        if not is_list(args):
            raise LispError("apply の第2引数はリストです: %s" % write(args))
        return apply_fn(fn, list(args))

    env.define("eval", Primitive("eval", prim_eval, (1, 2), kind="橋"))
    env.define("apply", Primitive("apply", prim_apply, 2, kind="橋"))
    env.define(T, T)
    env.define("nil", NIL)
    return env


BUILTIN_NAMES = frozenset(
    ("atom", "eq", "car", "cdr", "cons", "eval", "apply", T, "nil")
)


# ------------------------------------------------------------------------ REPL
HELP = """\
7つの公理:
  (atom x)          x がアトム（記号・()・関数）なら t、リストなら ()
  (eq x y)          ふたつのアトムが同じなら t、ちがえば ()
  (car xs)          リストの先頭
  (cdr xs)          リストの先頭を除いた残り
  (cons x xs)       x を先頭に足した新しいリスト
  (quote x)  'x     x を評価せずそのまま返す
  (cond (p e) ...)  p を順に試し、最初に真になった節の e を返す

ふたつの形式:
  (lambda (x y) 本体)   名前のない関数。値なので、渡すことも返すこともできる
  (label 名 式)         式の中から自分自身を名前で呼べる ── 再帰はここから生まれる

ふたつの橋（公理ではない）:
  (eval e a)      データ e を式として評価する。a は ((名前 値) ...) の連想リスト
                  省略すると大域環境だけで評価する。プログラムはデータでもある
  (apply f xs)    関数 f を、評価済みの引数のリスト xs に適用する

真偽:  () が偽。それ以外はすべて真。t と nil は自分自身に評価される。

例:
  ((lambda (x) (cons x (cons x '()))) '木)      -> (木 木)
  (label 数 (lambda (xs)
    (cond ((atom xs) '())
          (t (cons '一 (数 (cdr xs)))))))       ; 再帰する関数
  (eval '(car x) '((x (雪 が 降る))))            -> 雪
  (apply car '((雪 が 降る)))                    -> 雪
  (eval (cons 'cons (cons ''夜 (cons ''(が 明ける) nil))))  -> (夜 が 明ける)

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

    print("Po-Lisp 語の版 + lambda / label + eval — :help で説明、:quit で終了。")
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
