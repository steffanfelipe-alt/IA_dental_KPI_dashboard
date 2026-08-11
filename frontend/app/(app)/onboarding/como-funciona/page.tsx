"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

function DocumentIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-5 w-5"
    >
      <path d="M7 3h7l5 5v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" />
      <path d="M14 3v5h5M9 13h6M9 17h6" />
    </svg>
  );
}

function ScanIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-5 w-5"
    >
      <path d="M4 8V5a1 1 0 0 1 1-1h3M20 8V5a1 1 0 0 1-1-1h-3M4 16v3a1 1 0 0 0 1 1h3M20 16v3a1 1 0 0 1-1 1h-3M4 12h16" />
    </svg>
  );
}

function ReportIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-5 w-5"
    >
      <path d="M4 19V6a1 1 0 0 1 1-1h14a1 1 0 0 1 1 1v13" />
      <path d="M8 15v-3M12 15V9M16 15v-5M4 19h16" />
    </svg>
  );
}

const secciones = [
  {
    icon: DocumentIcon,
    titulo: "Qué vas a subir",
    texto:
      "Planillas de turnos y facturación (Excel o CSV), PDFs de tu sistema de gestión, o directo fotos de recetarios y fichas — lo que ya tengas, no hace falta que esté ordenado.",
  },
  {
    icon: ScanIcon,
    titulo: "Qué hace el sistema con eso",
    texto:
      "Extrae las variables clave de cada archivo (turnos, ausentismo, facturación, pacientes nuevos, etc.), las cruza con un set fijo de fórmulas de indicadores odontológicos y las compara contra benchmarks reales del mercado argentino.",
  },
  {
    icon: ReportIcon,
    titulo: "Qué te va a devolver",
    texto:
      "Un diagnóstico con las anomalías que encuentra en tu clínica (por ejemplo: fuga de pacientes, ausentismo alto, rentabilidad baja en algún sillón), la hipótesis detrás de cada una y qué tan sólida es la evidencia. Nunca inventa soluciones.",
  },
];

/**
 * First real explanation of the product before it asks for consent —
 * sets expectations so "aceptar el DPA/BAA" isn't the first thing a
 * new user reads with zero context on what's being processed or why.
 */
export default function ComoFuncionaPage() {
  const router = useRouter();

  function handleContinue() {
    router.push("/onboarding/consent");
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <Card>
        <div className="space-y-6">
          <div>
            <h1 className="text-2xl font-semibold text-ink-900">Cómo funciona</h1>
            <p className="text-sm text-ink-600">
              El objetivo de esta primera fase del sistema es simple: que con datos reales de tu clínica
              de períodos anteriores entiendas dónde están tus fortalezas y puntos débiles, para luego
              brindarte soluciones que optimicen tu sistema de manera precisa.
            </p>
          </div>

          <ul className="space-y-4">
            {secciones.map(({ icon: Icon, titulo, texto }) => (
              <li key={titulo} className="flex gap-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary-50 text-primary-500">
                  <Icon />
                </span>
                <div>
                  <p className="text-sm font-medium text-ink-900">{titulo}</p>
                  <p className="text-sm text-ink-600">{texto}</p>
                </div>
              </li>
            ))}
          </ul>

          <Button type="button" onClick={handleContinue}>
            Entendido, continuar <span aria-hidden="true">→</span>
          </Button>
        </div>
      </Card>
    </main>
  );
}
