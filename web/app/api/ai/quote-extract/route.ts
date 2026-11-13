import { generateText, Output } from "ai";
import { z } from "zod";
import { NextRequest, NextResponse } from "next/server";

const fields = z.object({
  rate_per_km_vnd: z.number().nullable(), callout_fee_vnd: z.number().nullable(), minimum_fare_vnd: z.number().nullable(),
  stop_fee_vnd: z.number().nullable(), vat_rate_assumption: z.number().nullable(),
  return_trip_rule: z.enum(["ONE_WAY", "ROUND_TRIP"]), currency: z.string().default("VND"),
  vehicle_class_hint: z.string().nullable(), validity_hint: z.string().nullable(), assumptions: z.array(z.string()).default([]),
});

export async function POST(request: NextRequest) {
  const payload = await request.json() as { text?: string };
  const text = payload.text?.trim();
  if (!text || text.length < 3 || text.length > 10000) return NextResponse.json({ detail: "Quote text must contain 3 to 10,000 characters" }, { status: 422 });
  if (!process.env.AI_GATEWAY_API_KEY || !process.env.FLEETMIX_AI_MODEL) {
    const response = await fetch(`${process.env.FLEETMIX_API_URL ?? "http://127.0.0.1:8000"}/api/ai/quote-extract`, {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ text }), cache: "no-store",
    });
    return NextResponse.json(await response.json(), { status: response.status });
  }
  const model = process.env.FLEETMIX_AI_MODEL;
  try {
    const result = await generateText({ model,
      system: "Extract only carrier quote terms from source text. Keep currency as VND unless explicitly stated. Never invent missing values: use null. Return numeric values without separators. Flag uncertainty in assumptions. This is a draft for human review, never a booking or legal interpretation.",
      prompt: text, output: Output.object({ schema: fields }) });
    return NextResponse.json({ source: "AI_GATEWAY", ai_model_used: true, confidence: null, needs_human_review: true, fields: result.output,
      note: "AI extracted a draft. Verify source, currency, units, tax and validity before saving." });
  } catch (error) {
    return NextResponse.json({ detail: error instanceof Error ? error.message : "AI quote extraction failed" }, { status: 502 });
  }
}
