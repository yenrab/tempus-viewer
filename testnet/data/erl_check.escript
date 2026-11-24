#!/usr/bin/env escript
%% Decodes every .etf under out/ with Erlang and prints a one-line summary of each case's shape.
main([Dir]) ->
    Files = filelib:wildcard(filename:join([Dir, "**", "*.etf"])),
    Bad = lists:filter(fun(F) ->
        {ok, B} = file:read_file(F),
        try binary_to_term(B), false catch _:_ -> true end
    end, Files),
    io:format("~p files decoded, ~p failed to decode~n", [length(Files) - length(Bad), length(Bad)]),
    [io:format("  cannot decode: ~s~n", [F]) || F <- Bad],
    {ok, P} = file:read_file(filename:join([Dir, "cases", "pid_in_reply.etf"])),
    T = binary_to_term(P),
    io:format("pid_in_reply reads as: ~p~n", [T]).
