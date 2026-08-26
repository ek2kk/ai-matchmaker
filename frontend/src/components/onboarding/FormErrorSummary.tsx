type Props = {
  messages: string[];
};

export function FormErrorSummary({ messages }: Props) {
  if (messages.length === 0) {
    return null;
  }
  return (
    <div
      role="alert"
      aria-live="polite"
      className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-800"
    >
      <p className="font-medium">Please fix the following:</p>
      <ul className="mt-1 list-disc pl-5">
        {messages.map((message) => (
          <li key={message}>{message}</li>
        ))}
      </ul>
    </div>
  );
}
