import type { ComponentType, SVGProps } from "react";
import {
  CarIcon,
  ChatIcon,
  DocumentIcon,
  HomeIcon,
  IdCardIcon,
  LinkIcon,
  LockIcon,
  PassportIcon,
  PhoneIcon,
  QuestionIcon,
  RouteIcon,
  ScrollIcon,
  ShieldIcon,
  SteeringIcon,
} from "@/components/icons";

type IconType = ComponentType<SVGProps<SVGSVGElement>>;

// İşlem adları config/process_types.json ile aynıdır; `ready` alanı yol haritası üretimi için
// kaynakları toplanmış (MVP) işlemleri gösterir.
const PROCESSES: { name: string; icon: IconType; ready: boolean }[] = [
  { name: "Miras yoluyla araç devri", icon: CarIcon, ready: true },
  { name: "Mirasçılık belgesi (veraset ilamı)", icon: ScrollIcon, ready: true },
  { name: "İkinci el araç alım-satım devri", icon: SteeringIcon, ready: false },
  { name: "Pasaport başvurusu ve yenileme", icon: PassportIcon, ready: false },
  { name: "Yurt dışından getirilen telefonun IMEI kaydı", icon: PhoneIcon, ready: false },
  { name: "İkametgâh / yerleşim yeri belgesi", icon: HomeIcon, ready: false },
  { name: "Kimlik kartı yenileme", icon: IdCardIcon, ready: false },
  { name: "Ehliyet yenileme / değişimi", icon: DocumentIcon, ready: false },
];

const STEPS: { title: string; text: string; icon: IconType }[] = [
  {
    title: "Durumunuzu anlatın",
    text: "Form doldurmak yok. Ne yapmak istediğinizi günlük dilde birkaç cümleyle yazın.",
    icon: ChatIcon,
  },
  {
    title: "Kısa sorulara yanıt verin",
    text: "Gerekirse en fazla üç kısa soru sorulur; böylece size uymayan adımlar elenir.",
    icon: QuestionIcon,
  },
  {
    title: "Yol haritanızı alın",
    text: "Gerekli evraklar, gidilecek kurum ve adımların sırası; her adımın altında resmi kaynağı.",
    icon: RouteIcon,
  },
];

const PRINCIPLES: { title: string; text: string; icon: IconType }[] = [
  {
    title: "Yalnızca resmi kaynaklar",
    text: "Bilgiler kamu kurumlarının ve meslek kuruluşlarının sitelerinden, mevzuattan derlenir.",
    icon: ShieldIcon,
  },
  {
    title: "Her adım kaynaklı",
    text: "Kaynakta doğrulanamayan bilgi gösterilmez; her adımın yanında dayandığı sayfa bulunur.",
    icon: LinkIcon,
  },
  {
    title: "Kişisel veri istenmez",
    text: "T.C. kimlik numarası, plaka veya adres sorulmaz; yanlışlıkla yazılanlar otomatik gizlenir.",
    icon: LockIcon,
  },
];

const SOURCES = [
  "Türkiye Noterler Birliği",
  "Emniyet Genel Müdürlüğü",
  "Gelir İdaresi Başkanlığı",
  "Mevzuat Bilgi Sistemi",
  "Nüfus ve Vatandaşlık İşleri",
  "e-Devlet Kapısı",
  "Bilgi Teknolojileri ve İletişim Kurumu",
  "Resmî Gazete",
  "Adalet Bakanlığı",
  "Ticaret Bakanlığı",
];

function SectionHeading({ id, eyebrow, title }: { id: string; eyebrow: string; title: string }) {
  return (
    <div className="mb-8 flex flex-col gap-2">
      <p className="text-sm font-semibold tracking-wide text-accent uppercase">{eyebrow}</p>
      <h2 id={id} className="text-2xl font-semibold tracking-tight sm:text-3xl">
        {title}
      </h2>
    </div>
  );
}

export function HowItWorks() {
  return (
    <section id="nasil-calisir" aria-labelledby="nasil-baslik" className="scroll-mt-20">
      <SectionHeading id="nasil-baslik" eyebrow="Nasıl çalışır" title="Üç adımda yol haritası" />
      <ol className="grid gap-4 sm:grid-cols-3">
        {STEPS.map(({ title, text, icon: StepIcon }, index) => (
          <li
            key={title}
            className="relative flex flex-col gap-3 rounded-2xl border border-border bg-background p-6"
          >
            <div className="flex items-center justify-between">
              <span className="flex size-11 items-center justify-center rounded-xl bg-accent-soft text-accent-soft-fg">
                <StepIcon className="size-6" />
              </span>
              <span aria-hidden="true" className="text-4xl font-semibold text-border">
                {index + 1}
              </span>
            </div>
            <h3 className="text-lg font-semibold">{title}</h3>
            <p className="text-muted">{text}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}

export function ProcessGrid() {
  return (
    <section id="islemler" aria-labelledby="islemler-baslik" className="scroll-mt-20">
      <SectionHeading
        id="islemler-baslik"
        eyebrow="İşlemler"
        title="Hangi işlemlerde yardımcı olur?"
      />
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {PROCESSES.map(({ name, icon: ProcessIcon, ready }) => (
          <li
            key={name}
            className={`flex flex-col gap-4 rounded-2xl border p-5 ${
              ready ? "border-accent/40 bg-accent-soft/40" : "border-border bg-surface"
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <span
                className={`flex size-10 items-center justify-center rounded-xl ${
                  ready ? "bg-accent text-accent-foreground" : "bg-background text-muted"
                }`}
              >
                <ProcessIcon className="size-5" />
              </span>
              <span
                className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                  ready ? "bg-accent-soft text-accent-soft-fg" : "bg-background text-muted"
                }`}
              >
                {ready ? "Hazır" : "Yakında"}
              </span>
            </div>
            <p className="font-medium">{name}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function Principles() {
  return (
    <section id="ilkeler" aria-labelledby="ilkeler-baslik" className="scroll-mt-20">
      <SectionHeading id="ilkeler-baslik" eyebrow="Güven" title="Neye dayanıyor?" />
      <div className="grid gap-4 sm:grid-cols-3">
        {PRINCIPLES.map(({ title, text, icon: PrincipleIcon }) => (
          <div key={title} className="flex flex-col gap-3">
            <span className="flex size-11 items-center justify-center rounded-xl bg-accent-soft text-accent-soft-fg">
              <PrincipleIcon className="size-6" />
            </span>
            <h3 className="text-lg font-semibold">{title}</h3>
            <p className="text-muted">{text}</p>
          </div>
        ))}
      </div>
      <div className="mt-10 rounded-2xl border border-border bg-surface p-6">
        <p className="mb-4 text-sm font-medium">
          Bilgi yalnızca şu kurumların resmi sitelerinden alınır
        </p>
        <ul className="flex flex-wrap gap-2">
          {SOURCES.map((source) => (
            <li
              key={source}
              className="rounded-full border border-border bg-background px-3 py-1.5 text-sm text-muted"
            >
              {source}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
