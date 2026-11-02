# Common passwords

`common_passwords.txt` is the UK National Cyber Security Centre's list of the 100,000 most commonly
used passwords (published by the NCSC, Crown copyright, Open Government Licence v3.0; the copy used
is the one mirrored in the SecLists project, `100k-most-used-passwords-NCSC.txt`), in lower case,
one per line, duplicates removed.

It is the fallback when the Have I Been Pwned range service cannot be reached (plan 4.2). The whole
list is kept, not only the entries of 12 characters or more that today's minimum length lets
through, so the check stays complete if the minimum is ever lowered.
