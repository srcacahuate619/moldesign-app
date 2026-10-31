# FEP-06-HUM — deviations from the pre-registration

[`REGISTRO_PREVIO.md`](REGISTRO_PREVIO.md) stays exactly as it was committed before any package was generated. What has changed
since then is listed here, in order. The full log, including the parts that would reveal the control, is published with the
answer key when the round closes.

None of these entries changes the ten packages, the answer key or its SHA-256, the decision rule, or the credit.

## 2026-10-25 — two generations discarded before anyone saw them

The first generation had a generator error in one package and a defect in another (the English dossier PDF could not lay out
one table row; fixed in the product, with a test). The second left one package without its source structure, because the
capsule prepared the receptor from a copy that does not ship in the installer. Both were set aside unpublished, and the ten
packages were generated again, so all ten come from one build. The third generation is the one in `packages/`.

## 2026-10-26 — reviews are sent privately, not by issue

Section 5 of the pre-registration admits a review "that arrives through the challenge's issue template". Issues are public, so
a reviewer could read what earlier reviewers found, including which package is the control, and the reviews would stop being
independent. Reviews now arrive by Reddit private message or email, with [`REVIEW_FORM.md`](REVIEW_FORM.md), which asks for the
same fields plus one question: whether you saw another review. A "yes" does not exclude you; it is reported separately. The
issue template is now for signing up only.

In the same change, the package verifier stopped needing the backend: it runs with Python 3 and its standard library. What it
checks did not change.

## 2026-10-31 — the instructions now say what the rules already said

An audit of the instructions against the pre-registration, the packages and the sealed key found gaps in the text. These
entries add no rule that the sealed documents did not already contain:

- the README now lists every INCONCLUSIVE case (it left out "fewer than 2 reviews of the control package" and "any other case")
  and defines admitted review, silent loss and false alarm;
- it defines the four need states and restates that a silent loss rules out `READY_TO_PREPARE`, as in the earlier rounds;
- it says that the answer key and the material of the earlier LLM rounds are not allowed, which the sealed key already said;
- it translates the Spanish states that appear in the packages, and it says that `main` has moved on from `b361d730`;
- the sign-up template no longer asks GitHub for a label that does not exist, and its file is now named `fep06-hum-signup.yml`;
- the video that the package table mentioned is now linked.

One entry is a new procedure, because the assignment list did not cover it. If an assigned reviewer says they can't finish, or
14 days pass without a review, their packages are offered to the next person who signs up, ahead of the next pair on the list.
A review from the original reviewer still counts if it arrives before the round closes. This keeps the packages that the
decision rule depends on from being left without reviews.
