export const DISCLAIMER_TEXT =
  "Bilgiler resmi kaynaklardan derlenmiştir; işlem öncesinde ilgili kurumdan teyit ediniz. Hukuki tavsiye değildir.";

export function Disclaimer() {
  return (
    <p role="note" className="text-sm text-muted">
      <strong className="font-semibold text-foreground">Uyarı:</strong> {DISCLAIMER_TEXT}
    </p>
  );
}
