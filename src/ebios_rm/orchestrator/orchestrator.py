"""The orchestrator — absolute rule (conception §10.2).

Workshop N -> Mission State -> Orchestrator -> Workshop N+1.
Never a direct call from one workshop to the next. This is what gives, with
no extra mechanism: pause/resume at any point, replay of a single workshop,
version history, and insertion of human validation points without ever
touching a workshop's code.
"""
