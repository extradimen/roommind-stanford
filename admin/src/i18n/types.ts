import { zh } from "./locales/zh";

type DeepStringify<T> = {
  [K in keyof T]: T[K] extends readonly (infer U)[]
    ? U extends string
      ? string[]
      : DeepStringify<T[K]>
    : T[K] extends string
      ? string
      : DeepStringify<T[K]>;
};

export type Messages = DeepStringify<typeof zh>;
