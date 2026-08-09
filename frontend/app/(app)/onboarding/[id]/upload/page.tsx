import { Upload } from "@/components/Upload";

export default async function UploadPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <Upload clinicaId={id} />;
}
