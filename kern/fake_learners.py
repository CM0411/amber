"""
Fake learners — to test the measuring loop before a learning core exists.

These learn nothing in the sense this project means. They fit a little rule
to a series of examples and use it afterwards. That is exactly enough to
establish whether the measuring loop measures what it claims to measure.

Two of them, and the difference between them is the entire test:

  * `OneRuleLearner` remembers one rule. Learning something new erases the
    old — a caricature of catastrophic forgetting
  * `RulePerKindLearner` remembers a rule per family and grade, and so
    forgets nothing

If the measuring loop cannot tell those two apart, it measures nothing.

They only do arithmetic and puzzles. Code problems ask for imitating a
program and no little rule can — that family stays at zero, which at once
tests whether the loop handles "nothing was learned here" cleanly.

English successor of namaakleerders.py; toets-migratie.py enforces that
both answer identically.
"""

import re


def _numbers(problem):
    return [int(x) for x in re.findall(r"-?\d+", problem)]


# --- the rules that get tried ------------------------------------------------
# Each takes the numbers from the problem and returns an answer, or None
# when not applicable.

def _sum(n):
    return sum(n)


def _difference(n):
    return n[0] - n[1] if len(n) >= 2 else None


def _product(n):
    return n[0] * n[1] if len(n) >= 2 else None


def _product_plus(n):
    return n[0] * n[1] + n[2] if len(n) >= 3 else None


def _product_minus(n):
    return n[0] * n[1] - n[2] if len(n) >= 3 else None


def _parens(n):
    return (n[0] + n[1]) * n[2] - n[3] if len(n) >= 4 else None


def _row_fixed(n):
    return n[-1] + (n[1] - n[0]) if len(n) >= 2 else None


def _row_times(n):
    if len(n) >= 2 and n[0] != 0 and n[1] % n[0] == 0:
        return n[-1] * (n[1] // n[0])
    return None


def _row_sum_two(n):
    return n[-1] + n[-2] if len(n) >= 2 else None


def _row_woven(n):
    return n[-2] + (n[2] - n[0]) if len(n) >= 3 else None


def _row_second_order(n):
    if len(n) < 3:
        return None
    first = [n[i + 1] - n[i] for i in range(len(n) - 1)]
    return n[-1] + first[-1] + (first[1] - first[0])


RULES = {
    "som": _sum,
    "verschil": _difference,
    "product": _product,
    "product_plus": _product_plus,
    "product_min": _product_minus,
    "haakjes": _parens,
    "rij_vast": _row_fixed,
    "rij_maal": _row_times,
    "rij_som_twee": _row_sum_two,
    "rij_gevlochten": _row_woven,
    "rij_tweede_orde": _row_second_order,
}


def _best_rule(tasks_):
    """Which rule explains these examples best?"""
    best, best_score = None, 0.0
    for name, rule in RULES.items():
        right = 0
        for t in tasks_:
            try:
                outcome = rule(_numbers(t.opgave))
            except (IndexError, ZeroDivisionError):
                outcome = None
            if outcome is not None and t.nakijk(outcome):
                right += 1
        score = right / len(tasks_)
        if score > best_score:
            best, best_score = name, score
    return best, best_score


def _apply(name, task):
    if name is None:
        return ""
    try:
        outcome = RULES[name](_numbers(task.opgave))
    except (IndexError, ZeroDivisionError):
        return ""
    return "" if outcome is None else str(outcome)


class OneRuleLearner:
    """Remembers one rule. Learning something new erases the old."""

    def __init__(self):
        self.rule = None

    def learn(self, tasks_):
        name, score = _best_rule(tasks_)
        if name is not None:
            self.rule = name           # the old is gone with this

    def answer_one(self, task):
        return _apply(self.rule, task)

    # migration aliases — drop when the Dutch modules are gone
    leer = learn
    antwoord = answer_one


class RulePerKindLearner:
    """Remembers a rule per family and grade. So forgets nothing."""

    def __init__(self):
        self.rules = {}

    def learn(self, tasks_):
        kind = (tasks_[0].familie, tasks_[0].graad)
        name, score = _best_rule(tasks_)
        if name is not None:
            self.rules[kind] = name

    def answer_one(self, task):
        return _apply(self.rules.get((task.familie, task.graad)), task)

    leer = learn
    antwoord = answer_one


class MemorizerLearner:
    """Literally remembers the problems it has seen.

    Does not generalize. On the benchmark it therefore scores zero however
    much it has learned — which is exactly the test of whether the
    benchmark is truly fenced off.
    """

    def __init__(self):
        self.table = {}

    def learn(self, tasks_):
        for t in tasks_:
            self.table[t.opgave] = t.oplossing

    def answer_one(self, task):
        return self.table.get(task.opgave, "")

    leer = learn
    antwoord = answer_one
