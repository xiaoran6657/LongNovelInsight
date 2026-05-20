import { useQuery } from "@tanstack/react-query";
import { getStorage } from "../../api/parse";
import LoadingBlock from "../../components/LoadingBlock";

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

interface Props {
  topicId: string;
}

export default function StoragePanel({ topicId }: Props) {
  const { data: storageData, isLoading } = useQuery({
    queryKey: ["storage", topicId],
    queryFn: () => getStorage(topicId),
    enabled: !!topicId,
  });

  if (isLoading) return <LoadingBlock text="Loading storage..." />;

  const ts = storageData?.topics?.[0];

  return (
    <div className="card">
      <h3>Storage</h3>
      <p><strong>Total disk:</strong> {formatBytes(storageData?.total_disk_usage_bytes ?? 0)}</p>
      <p><strong>Database:</strong> {formatBytes(storageData?.database_size_bytes ?? 0)}</p>
      <p><strong>Data dir:</strong> {formatBytes(storageData?.data_dir_size_bytes ?? 0)}</p>
      {ts && (
        <>
          <p><strong>Novel:</strong> {formatBytes(ts.novel_size_bytes)}</p>
          <p><strong>Chunks:</strong> {formatBytes(ts.chunks_size_bytes)}</p>
          <p><strong>Analyses:</strong> {formatBytes(ts.analyses_size_bytes)}</p>
        </>
      )}
    </div>
  );
}
