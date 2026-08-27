/** Film grain + radial vignette. Sits in every section, above the image. */
export function Grain() {
  return (
    <>
      <div className="vignette" aria-hidden />
      <div className="grain" aria-hidden />
    </>
  );
}
