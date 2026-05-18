interface Props {
  text?: string;
}

export default function LoadingBlock({ text = "Loading..." }: Props) {
  return (
    <div className="card" style={{ textAlign: "center", padding: "2rem 1rem" }}>
      <p className="text-dim">{text}</p>
    </div>
  );
}
