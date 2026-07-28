ENV_ROOT = normpath(joinpath(@__DIR__, ".."))
ENV["JULIA_PKG_PRECOMPILE_AUTO"] = "0"

import Pkg

Pkg.activate(ENV_ROOT)
Pkg.instantiate()

using JSON
using TensorQEC

include(joinpath(@__DIR__, "support.jl"))
using .AutoQECTensorQECSupport

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

function parse_int_arg(parsed, key)
    value = tryparse(Int, require_arg(parsed, key))
    value === nothing && error("invalid integer for --$key")
    return value
end

function parse_shift_pairs_arg(parsed, key)
    raw = try
        JSON.parse(require_arg(parsed, key))
    catch exc
        if exc isa ArgumentError
            nothing
        else
            rethrow()
        end
    end
    raw === nothing && error("--$key must be valid JSON")
    raw isa Vector || error("--$key must decode to an array")
    pairs = Tuple{Int, Int}[]
    for entry in raw
        entry isa Vector || error("--$key entries must be arrays")
        length(entry) == 2 || error("--$key entries must have length 2")
        all(value -> value isa Integer, entry) || error("--$key entries must be integer pairs")
        push!(pairs, (Int(entry[1]), Int(entry[2])))
    end
    return Tuple(pairs)
end

function repetition_graph(distance)
    checks = [Int[i, i + 1] for i in 1:(distance - 1)]
    return SimpleTannerGraph(distance, checks)
end

function unrotated_surface_tanner(distance)
    rep = repetition_graph(distance)
    return product_graph(rep, rep)
end

function main(args)
    parsed = parse_args(args)
    code_id = require_arg(parsed, "code-id")
    output_root = require_arg(parsed, "output-root")

    local tanner
    local id
    local family_id
    local title
    local parameters
    local generator_parameters

    if code_id == "rotated-surface-code"
        distance = parse_int_arg(parsed, "distance")
        tanner = CSSTannerGraph(SurfaceCode(distance, distance))
        id = rotated_surface_slug(distance)
        family_id = "surface-code"
        title = "Rotated Surface Code d=$(distance)"
        parameters = Dict("distance" => distance, "layout" => "rotated")
        generator_parameters = copy(parameters)
    elseif code_id == "surface-code"
        distance = parse_int_arg(parsed, "distance")
        tanner = unrotated_surface_tanner(distance)
        id = unrotated_surface_slug(distance)
        family_id = "surface-code"
        title = "Surface Code d=$(distance)"
        parameters = Dict("distance" => distance, "layout" => "unrotated")
        generator_parameters = copy(parameters)
    elseif code_id == "bivariate-bicycle-code"
        m = parse_int_arg(parsed, "m")
        n = parse_int_arg(parsed, "n")
        vc = parse_shift_pairs_arg(parsed, "vc")
        hd = parse_shift_pairs_arg(parsed, "hd")
        tanner = CSSTannerGraph(BivariateBicycleCode(m, n, vc, hd))
        id = bbcode_slug(m, n)
        family_id = "bivariate-bicycle-code"
        title = "Bivariate Bicycle Code m=$(m) n=$(n)"
        parameters = Dict(
            "m" => m,
            "n" => n,
            "vc" => [[pair[1], pair[2]] for pair in vc],
            "hd" => [[pair[1], pair[2]] for pair in hd],
        )
        generator_parameters = copy(parameters)
    else
        error("unsupported --code-id: $code_id")
    end

    hx_payload, hz_payload = css_payloads(tanner)
    write_instance_bundle(
        output_root;
        id=id,
        code_id=code_id,
        family_id=family_id,
        title=title,
        parameters=parameters,
        generator_parameters=generator_parameters,
        hx_payload=hx_payload,
        hz_payload=hz_payload,
    )
end

main(ARGS)
