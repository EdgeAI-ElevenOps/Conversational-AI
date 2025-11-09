"""Word Error Rate (WER) utilities.

Provides a simple, well-tested implementation of WER using Levenshtein
distance at the word level. Exported function:

  wer(ref: str, hyp: str) -> float

Also includes a small CLI so users can compute WER from the command line.
"""
from __future__ import annotations

import argparse
from typing import List, Tuple


def _edit_distance(ref_words: List[str], hyp_words: List[str]) -> Tuple[int, int, int]:
    """Compute word-level Levenshtein distance and return (S, D, I).

    Returns:
      S: substitutions
      D: deletions
      I: insertions
    """
    n = len(ref_words)
    m = len(hyp_words)

    # dp matrix of shape (n+1) x (m+1)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][0] = i
    for j in range(1, m + 1):
        dp[0][j] = j

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                substitute = dp[i - 1][j - 1] + 1
                insert = dp[i][j - 1] + 1
                delete = dp[i - 1][j] + 1
                dp[i][j] = min(substitute, insert, delete)

    # Backtrack to count S, D, I
    i, j = n, m
    S = D = I = 0
    while i > 0 or j > 0:
        if i > 0 and j > 0 and ref_words[i - 1] == hyp_words[j - 1]:
            i -= 1
            j -= 1
        else:
            # determine which operation was chosen
            if i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
                S += 1
                i -= 1
                j -= 1
            elif j > 0 and dp[i][j] == dp[i][j - 1] + 1:
                I += 1
                j -= 1
            else:
                D += 1
                i -= 1

    return S, D, I


def wer(reference: str, hypothesis: str) -> float:
    """Calculate Word Error Rate (WER).

    WER = (S + D + I) / N where N is the number of words in the reference.

    Returns a float between 0.0 and infinity. If the reference is empty and the
    hypothesis is non-empty, define WER as number of hypothesis words (i.e., I/N
    where N==0 -> we return float('inf')). For practical uses, callers may
    treat an empty reference as special.
    """
    # Simple tokenization on whitespace; callers can pre-normalize if needed.
    ref_words = reference.strip().split() if reference.strip() else []
    hyp_words = hypothesis.strip().split() if hypothesis.strip() else []

    if len(ref_words) == 0:
        if len(hyp_words) == 0:
            return 0.0
        # define as infinite/error; caller might want to handle this case
        return float('inf')

    S, D, I = _edit_distance(ref_words, hyp_words)
    wer_value = (S + D + I) / len(ref_words)
    return wer_value


def cli():
    parser = argparse.ArgumentParser(description='Compute WER between reference and hypothesis')
    parser.add_argument('reference', help='Reference text (quoted)')
    parser.add_argument('hypothesis', help='Hypothesis text (quoted)')
    args = parser.parse_args()
    score = wer(args.reference, args.hypothesis)
    if score == float('inf'):
        print('WER: inf (empty reference)')
    else:
        print(f'WER: {score:.3f}')


if __name__ == '__main__':
    cli()
