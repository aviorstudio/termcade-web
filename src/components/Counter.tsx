import { component$, useSignal } from "@builder.io/qwik";

export const Counter = component$(() => {
  const count = useSignal(0);

  return (
    <div class="flex flex-col items-center gap-6">
      <span class="text-7xl font-extralight tabular-nums text-gray-800">
        {count.value}
      </span>
      <div class="flex items-center gap-3">
        <button
          class="w-12 h-12 rounded-xl bg-white border border-gray-200 text-xl font-medium text-gray-600 hover:bg-gray-50 hover:border-gray-300 active:scale-95 transition-all shadow-sm cursor-pointer"
          onClick$={() => count.value--}
        >
          −
        </button>
        <button
          class="w-12 h-12 rounded-xl bg-white border border-gray-200 text-xl font-medium text-gray-600 hover:bg-gray-50 hover:border-gray-300 active:scale-95 transition-all shadow-sm cursor-pointer"
          onClick$={() => count.value++}
        >
          +
        </button>
      </div>
    </div>
  );
});
