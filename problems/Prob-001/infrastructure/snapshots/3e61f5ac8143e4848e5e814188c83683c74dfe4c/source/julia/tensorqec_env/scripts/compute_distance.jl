ENV_ROOT = normpath(joinpath(@__DIR__, ".."))
ENV["JULIA_PKG_PRECOMPILE_AUTO"] = "0"

import Pkg

Pkg.activate(ENV_ROOT)
Pkg.instantiate()

using JSON
using TensorQEC

function parse_args(args)
    if isodd(length(args))
        error("expected explicit --flag value pairs")
    end

    parsed = Dict{String, String}()
    index = 1
    while index <= length(args)
        key = args[index]
        value = args[index + 1]
        startswith(key, "--") || error("unexpected argument: $key")
        parsed[key[3:end]] = value
        index += 2
    end
    return parsed
end

function require_arg(parsed, key)
    haskey(parsed, key) || error("missing required --$key")
    return parsed[key]
end

function load_dense_binary_matrix(path)
    payload = JSON.parsefile(path)
    payload["format"] == "dense_binary_matrix" || error("unsupported matrix format: $path")
    data = payload["data"]
    data isa Vector || error("matrix data must be an array: $path")
    return Mod2.(hcat(data...)')
end

function main(args)
    parsed = parse_args(args)
    hx = load_dense_binary_matrix(require_arg(parsed, "hx-path"))
    hz = load_dense_binary_matrix(require_arg(parsed, "hz-path"))
    tanner = CSSTannerGraph(SimpleTannerGraph(hx), SimpleTannerGraph(hz))
    JSON.print(stdout, Dict("distance" => Int(code_distance(tanner))))
    write(stdout, '\n')
end

main(ARGS)
