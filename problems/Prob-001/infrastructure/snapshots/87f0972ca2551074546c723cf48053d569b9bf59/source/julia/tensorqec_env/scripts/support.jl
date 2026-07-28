module AutoQECTensorQECSupport

using Dates
using JSON

export bbcode_slug
export css_payloads
export matrix_payload
export normalize_slug_token
export normalized_now_utc
export rotated_surface_slug
export unrotated_surface_slug
export write_instance_bundle

function normalize_slug_token(value)
    text = lowercase(string(value))
    text = replace(text, "_" => "-", " " => "-")
    text = replace(text, r"[^a-z0-9-]" => "")
    text = replace(text, r"-+" => "-")
    return strip(text, '-')
end

function normalized_now_utc()
    timestamp = Dates.now(Dates.UTC)
    return Dates.format(timestamp, dateformat"yyyy-mm-ddTHH:MM:SS") * "Z"
end

function matrix_payload(matrix)
    dense = Int.(getproperty.(matrix, :x))
    return Dict(
        "format" => "dense_binary_matrix",
        "n_rows" => size(dense, 1),
        "n_cols" => size(dense, 2),
        "data" => [vec(dense[row, :]) for row in axes(dense, 1)],
    )
end

function css_payloads(tanner)
    return matrix_payload(tanner.stgx.H), matrix_payload(tanner.stgz.H)
end

rotated_surface_slug(distance::Integer) = "rotated-surface-code-d$(normalize_slug_token(distance))"
unrotated_surface_slug(distance::Integer) = "surface-code-d$(normalize_slug_token(distance))"
bbcode_slug(m::Integer, n::Integer) =
    "bivariate-bicycle-code-m$(normalize_slug_token(m))-n$(normalize_slug_token(n))"

function _write_json(path, payload)
    open(path, "w") do io
        JSON.print(io, payload, 2)
        write(io, '\n')
    end
end

function write_instance_bundle(
    output_root;
    id,
    code_id,
    family_id,
    title,
    parameters,
    generator_parameters,
    hx_payload,
    hz_payload,
)
    mkpath(output_root)

    instance_payload = Dict(
        "id" => id,
        "code_id" => code_id,
        "family_id" => family_id,
        "title" => title,
        "instance_kind" => "finite_css_instance",
        "matrix_format" => "dense_binary_json",
        "artifacts" => Dict(
            "hx" => "hx.json",
            "hz" => "hz.json",
        ),
        "parameters" => parameters,
        "derived_properties" => Dict(
            "distance" => nothing,
            "n" => hx_payload["n_cols"],
            "kx" => nothing,
            "kz" => nothing,
            "mx" => hx_payload["n_rows"],
            "mz" => hz_payload["n_rows"],
        ),
        "provenance" => Dict(
            "generator" => "tensorQEC.jl",
            "generator_env" => "julia/tensorqec_env",
            "generated_at" => normalized_now_utc(),
            "generator_script" => "julia/tensorqec_env/scripts/generate_instance.jl",
            "generator_parameters" => generator_parameters,
        ),
    )

    _write_json(joinpath(output_root, "instance.json"), instance_payload)
    _write_json(joinpath(output_root, "hx.json"), hx_payload)
    _write_json(joinpath(output_root, "hz.json"), hz_payload)
end

end
