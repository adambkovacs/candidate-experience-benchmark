---
description: Clef-flash is a fast 9B multimodal decision model that turns a state and a schema of typed questions into decisions. It reads the state as text, JSON, images, or video, and returns a probability for every allowed option of every question.
title: clef-flash
image: https://developers.cloudflare.com/og-docs.png
---

[Skip to content](#main-content)

> Documentation Index  
> Fetch the complete documentation index at: https://developers.cloudflare.com/llms.txt  
> Use this file to discover all available pages before exploring further.

![Cloudflare logo](https://developers.cloudflare.com/_astro/cloudflare.DP8rkHys.svg)

# clef-flash

Text Generation • Cloudflare

Copy as Markdown| [View as Markdown](https://developers.cloudflare.com/workers-ai/models/clef-flash/index.md)| [Agent setup](https://developers.cloudflare.com/agent-setup/)

`@cf/cloudflare/clef-flash`

- Cloudflare-hosted
- Vision

Clef-flash is a fast 9B multimodal decision model that turns a state and a schema of typed questions into decisions. It reads the state as text, JSON, images, or video, and returns a probability for every allowed option of every question.

| Model Info | |
| --- | --- |
| Context Window [ ↗](https://developers.cloudflare.com/workers-ai/platform/glossary/) | 65,536 tokens |
| Terms and License | [link ↗](https://huggingface.co/Cloudflare/clef-flash/blob/main/LICENSE) |
| More information | [link ↗](https://huggingface.co/Cloudflare/clef-flash) |
| Vision | Yes |
| Unit Pricing | $0.09 per M input tokens |

## Usage

```ts
export interface Env {
	AI: Ai;
}

export default {
	async fetch(request, env): Promise<Response> {
		const response = await env.AI.run("@cf/cloudflare/clef-flash", {
			model: "clef-flash",
			state: "Checkout has been failing for every customer for the last hour.",
			questions: {
				urgent: {
					type: "noul",
					instructions: "Is this support request urgent?",
				},
				team: {
					type: "choice",
					instructions: "Which team should handle this request?",
					criteria: {
						billing: "Payments, invoices, and refunds",
						technical: "Outages, errors, and configuration",
						sales: "Plans and upgrades",
					},
				},
				severity: {
					type: "score",
					instructions: "How severe is the customer impact?",
					criteria: ["No impact", "Minor", "Major", "Critical"],
				},
			},
		});

		// response.answers.urgent   -> probability the request is urgent
		// response.answers.team     -> chosen team with per-option probabilities
		// response.answers.severity -> probability-weighted score (0 = lowest level)
		return Response.json(response);
	},
} satisfies ExportedHandler<Env>;
```

```py
import os
import requests

ACCOUNT_ID = "your-account-id"
AUTH_TOKEN = os.environ.get("CLOUDFLARE_AUTH_TOKEN")

response = requests.post(
    f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run/@cf/cloudflare/clef-flash",
    headers={"Authorization": f"Bearer {AUTH_TOKEN}"},
    json={
        "model": "clef-flash",
        "state": "Checkout has been failing for every customer for the last hour.",
        "questions": {
            "urgent": {
                "type": "noul",
                "instructions": "Is this support request urgent?",
            },
            "team": {
                "type": "choice",
                "instructions": "Which team should handle this request?",
                "criteria": {
                    "billing": "Payments, invoices, and refunds",
                    "technical": "Outages, errors, and configuration",
                    "sales": "Plans and upgrades",
                },
            },
            "severity": {
                "type": "score",
                "instructions": "How severe is the customer impact?",
                "criteria": ["No impact", "Minor", "Major", "Critical"],
            },
        },
    },
)
print(response.json())
```

```sh
curl https://api.cloudflare.com/client/v4/accounts/$CLOUDFLARE_ACCOUNT_ID/ai/run/@cf/cloudflare/clef-flash \
  -X POST \
  -H "Authorization: Bearer $CLOUDFLARE_AUTH_TOKEN" \
  -d '{
    "model": "clef-flash",
    "state": "Checkout has been failing for every customer for the last hour.",
    "questions": {
      "urgent": { "type": "noul", "instructions": "Is this support request urgent?" },
      "team": {
        "type": "choice",
        "instructions": "Which team should handle this request?",
        "criteria": {
          "billing": "Payments, invoices, and refunds",
          "technical": "Outages, errors, and configuration",
          "sales": "Plans and upgrades"
        }
      },
      "severity": {
        "type": "score",
        "instructions": "How severe is the customer impact?",
        "criteria": ["No impact", "Minor", "Major", "Critical"]
      }
    }
  }'
```

## Parameters

model

`string`requiredpattern: ^\\s\*(clef|clef-flash)\\s\*$Required. The model selector: "clef" for @cf/cloudflare/clef, "clef-flash" for @cf/cloudflare/clef-flash.

state

requiredRequired. The content to evaluate: a string, or structured data (object/array) such as records, chat logs, or application state. Long text state is truncated to fit the model's token limit.

▶questions{}

`object`requiredminProperties: 1maxProperties: 64Map of question id to a typed question (noul, choice, or score). 1 to 64 questions; ids may use letters, digits, '\_', '.', '-' (max 100 chars). Answers are returned under the same ids.

▶images\[]

`array`maxItems: 4Clef extension to the System One API. Optional embedded PNG, JPEG, or WebP images placed before the state (max 4; 4 MiB and 16 megapixels each, 8 MiB total decoded; whole request body max 13 MiB). Remote URLs are not accepted.

model

`string`The model that performed the evaluation.

▶answers{}

`object`One answer per question, keyed by the question ids from the request.

▶usage{}

`object`

## API Schemas (Raw)

Input [Open](https://developers.cloudflare.com/workers-ai/models/clef-flash/schema-input.json) [Download](https://developers.cloudflare.com/workers-ai/models/clef-flash/schema-input.json)

Output [Open](https://developers.cloudflare.com/workers-ai/models/clef-flash/schema-output.json) [Download](https://developers.cloudflare.com/workers-ai/models/clef-flash/schema-output.json)

Was this helpful?

YesNo

## On this page

[![](https://developers.cloudflare.com/_astro/logo.te5VL_aD.svg)Docs](https://developers.cloudflare.com/)

```json
{"@context":"https://schema.org","@type":"TechArticle","@id":"https://developers.cloudflare.com/workers-ai/models/clef-flash/#page","headline":"clef-flash","description":"Clef-flash is a fast 9B multimodal decision model that turns a state and a schema of typed questions into decisions. It reads the state as text, JSON, images, or video, and returns a probability for every allowed option of every question.","url":"https://developers.cloudflare.com/workers-ai/models/clef-flash/","inLanguage":"en","image":"https://developers.cloudflare.com/og-docs.png","publisher":{"@type":"Organization","name":"Cloudflare","description":"One platform for your apps, agents, and workforce. Build, secure, and scale without managing infrastructure","url":"https://www.cloudflare.com/","sameAs":["https://github.com/cloudflare","https://www.linkedin.com/company/cloudflare","https://x.com/cloudflare"],"logo":{"@type":"ImageObject","url":"https://developers.cloudflare.com/logo.svg"},"address":{"@type":"PostalAddress","streetAddress":"101 Townsend St","addressLocality":"San Francisco","addressRegion":"CA","postalCode":"94107","addressCountry":"US"},"contactPoint":[{"@type":"ContactPoint","contactType":"Customer Support","url":"https://support.cloudflare.com/","availableLanguage":["English"]},{"@type":"ContactPoint","contactType":"Sales","url":"https://www.cloudflare.com/contact/","availableLanguage":["English"]}]},"isPartOf":{"@type":"WebSite","@id":"https://developers.cloudflare.com/#website","name":"Cloudflare Docs","url":"https://developers.cloudflare.com/"}}
```
