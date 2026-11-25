// Strata decodes deterministically unless a request carries a seed: every
// trial of the same prompt would then be byte-identical. When PI_SAMPLING_SEED
// is set, add temperature (PI_SAMPLING_TEMPERATURE, default 1.0 as the
// Inkling model card recommends) and a per-request seed derived from it, so
// repeated trials are independent samples. Unset -> payload unchanged.
export default function (pi: any) {
  const base = process.env.PI_SAMPLING_SEED;
  if (!base) return;
  const temperature = Number(process.env.PI_SAMPLING_TEMPERATURE ?? "1.0");
  let n = 0;
  pi.on("before_provider_request", (event: any) => {
    n += 1;
    return { ...event.payload, temperature, seed: Number(base) * 1000 + n };
  });
}
