; eval を、語の版の Po-Lisp じたいで書く。
;   評価器そのものは公理7つ + lambda + label だけでできているので、v2
;   (polisp_word_lambda.py) でもそのまま動く。橋の eval を使う「もとのeval」の
;   3行だけが v3 専用。
;
;   読み込む:  python3 polisp_word_eval.py examples/polisp_word/eval.lisp
;        または REPL で  :load examples/polisp_word/eval.lisp
;   記号で書いた同じものは examples/polisp/eval.lisp

; 先に、橋としての eval を別の名前で捕まえておく（関数は値なのでこれができる）
:def もとのeval eval


; ------------------------------------------------------------------ 小さな道具
; eq はアトムしか比べない。だから空判定はまず atom で守る（McCarthy の null と同じ）
:def null   (lambda (x) (cond ((atom x) (eq x nil)) (t nil)))
:def cadr   (lambda (x) (car (cdr x)))
:def caddr  (lambda (x) (car (cdr (cdr x))))
:def caar   (lambda (x) (car (car x)))
:def cadar  (lambda (x) (car (cdr (car x))))
:def caddar (lambda (x) (car (cdr (cdr (car x)))))

:def append (label ap (lambda (x y)
  (cond ((null x) y)
        (t (cons (car x) (ap (cdr x) y))))))

; 名前の並びと値の並びから、連想リスト ((名前 値) ...) をつくる
; ドット対がないので、対は2要素のリストで表す
:def pair (label pr (lambda (names values)
  (cond ((null names) nil)
        (t (cons (cons (car names) (cons (car values) nil))
                 (pr (cdr names) (cdr values)))))))

; 連想リストから名前を引く
:def assoc (label as (lambda (k al)
  (cond ((null al) nil)
        ((eq k (caar al)) (cadar al))
        (t (as k (cdr al))))))


; ---------------------------------------------------------------------- 評価器
; cond の節を順に見て、最初に真になった節の結果を返す
:def evcon (label ec (lambda (c a)
  (cond ((eval (caar c) a) (eval (cadar c) a))
        (t (ec (cdr c) a)))))

; 引数の並びを、ひとつずつ評価する
:def evlis (label el (lambda (m a)
  (cond ((null m) nil)
        (t (cons (eval (car m) a) (el (cdr m) a))))))

; ここから下が eval そのもの。これで全部
:def eval (lambda (e a)
  (cond
    ; 記号なら、環境から値を引く
    ((atom e) (assoc e a))

    ; 先頭が記号なら、公理か、環境にある関数の名前
    ((atom (car e))
     (cond
       ((eq (car e) 'quote) (cadr e))
       ((eq (car e) 'atom)  (atom (eval (cadr e) a)))
       ((eq (car e) 'eq)    (eq   (eval (cadr e) a) (eval (caddr e) a)))
       ((eq (car e) 'car)   (car  (eval (cadr e) a)))
       ((eq (car e) 'cdr)   (cdr  (eval (cadr e) a)))
       ((eq (car e) 'cons)  (cons (eval (cadr e) a) (eval (caddr e) a)))
       ((eq (car e) 'cond)  (evcon (cdr e) a))
       ; 名前を引いて、その中身に置きかえてから、もういちど
       (t (eval (cons (assoc (car e) a) (cdr e)) a))))

    ; ((label 名 関数) 引数...) — 名前を環境に足してから、中身を呼ぶ
    ((eq (caar e) 'label)
     (eval (cons (caddar e) (cdr e))
           (cons (cons (cadar e) (cons (car e) nil)) a)))

    ; ((lambda (仮引数...) 本体) 引数...) — 引数を評価して環境に足し、本体を評価する
    ((eq (caar e) 'lambda)
     (eval (caddar e)
           (append (pair (cadar e) (evlis (cdr e) a)) a)))))


; ------------------------------------------------------------------ 動かしてみる
(eval '(car '(雪 が 降る)) '())                    ; 雪
(eval '(cons x '(が 降る)) '((x 雪)))              ; (雪 が 降る)
(eval '(cond ((atom x) 'ひとつ) ('t 'いくつも))
      '((x (朝 と 夜))))                           ; いくつも

; 名前のない関数
(eval '((lambda (x y) (cons x (cdr y))) '朝 '(夜 が 明ける)) '())   ; (朝 が 明ける)

; 環境に置いた関数を、名前で呼ぶ（この eval の世界では、関数もただのリスト）
(eval '(ふたつ '木) '((ふたつ (lambda (x) (cons x (cons x '()))))))  ; (木 木)

; label による再帰。空判定は (atom x) で書く
(eval '((label ap (lambda (x y)
          (cond ((atom x) y)
                ('t (cons (car x) (ap (cdr x) y))))))
        '(雪 が) '(降る))
      '())                                         ; (雪 が 降る)

; 同じ式を、言語じたいの評価器にも渡してみる。ふたつの eval が同じ答えを返す
(もとのeval '(car '(雪 が 降る)))                  ; 雪

; 二重に。橋の eval が、書いた eval を呼ぶ
(もとのeval '(eval '(car '(雪 が 降る)) '()))      ; 雪


; ------------------------------------------------ 詩をデータとして書き換えて、走らせる
:def mapcar (label mc (lambda (f xs)
  (cond ((null xs) nil)
        (t (cons (f (car xs)) (mc f (cdr xs)))))))

:def 置く (label sub (lambda (新 旧 x)
  (cond ((atom x) (cond ((eq x 旧) 新) (t x)))
        (t (mapcar (lambda (e) (sub 新 旧 e)) x)))))

:def 詩 '(cons '雪 (cons 'が (cons '降る '())))

(eval 詩 '())                         ; (雪 が 降る)
(eval (置く '雨 '雪 詩) '())          ; (雨 が 降る)
(eval (置く '止む '降る (置く '雨 '雪 詩)) '())   ; (雨 が 止む)
詩                                     ; もとの詩はそのまま残っている
