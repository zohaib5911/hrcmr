# Common passwords

`common_passwords.txt` holds the entries of the UK National Cyber Security Centre's list of the
100,000 most commonly used passwords (published by the NCSC, Crown copyright, Open Government
Licence v3.0; the copy used is the one mirrored in the SecLists project, `100k-most-used-passwords-NCSC.txt`)
that are 12 characters or longer, in lower case, one per line.

Why only those: the minimum password length is 12, so anything shorter is refused by the length
rule before this list is looked at. Keeping the long entries gives the same answers in a file of
about 15 KB instead of 800 KB.

It is the fallback when the Have I Been Pwned range service cannot be reached (plan 4.2).
