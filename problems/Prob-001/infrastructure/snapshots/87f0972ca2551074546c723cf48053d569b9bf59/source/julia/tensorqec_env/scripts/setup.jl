using Pkg

const ENV_ROOT = normpath(joinpath(@__DIR__, ".."))

Pkg.activate(ENV_ROOT)
Pkg.instantiate()

using TensorQEC

tanner = CSSTannerGraph(SurfaceCode(3, 3))

println("tensorqec_env ready")
println("environment=$(ENV_ROOT)")
println("surface_n=$(tanner.stgx.nq)")
println("surface_mx=$(tanner.stgx.ns)")
println("surface_mz=$(tanner.stgz.ns)")
