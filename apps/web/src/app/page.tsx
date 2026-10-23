// Geçici ana sayfa. Doğal dil giriş alanı ve yol haritası ekranı 5. aşamada eklenecek.
export default function Home() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center gap-4 px-4 py-16 sm:px-6">
      <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Evrakyol</h1>
      <p className="text-lg text-muted">
        Resmi işleminizi kendi cümlelerinizle anlatın; hangi evrakın gerektiğini, hangi kuruma
        gideceğinizi ve adımların sırasını resmi kaynaklarıyla birlikte gösterelim.
      </p>
      <p className="text-sm text-muted">Hazırlık aşamasında.</p>
    </div>
  );
}
