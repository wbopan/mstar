import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

// HeroUI's own look: Inter for UI text, a mono for code.
const sans = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
});

const mono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500", "700"],
});

const TITLE = "M★: Every Task Deserves Its Own Memory Harness";
const DESCRIPTION =
  "Interactive companion to the M★ paper (NeurIPS 2026): discovering a task-optimized memory harness for each LLM task via reflective code evolution.";

export const metadata: Metadata = {
  metadataBase: new URL("https://mstar.wenbo.io"),
  title: "M★ — Every Task Deserves Its Own Memory Harness",
  description: DESCRIPTION,
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    url: "https://mstar.wenbo.io/",
    siteName: "M★",
    title: TITLE,
    description: DESCRIPTION,
    images: [{ url: "/og.png", alt: "M★ system overview" }],
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: DESCRIPTION,
    images: ["/og.png"],
  },
  other: {
    citation_title: "M*: Every Task Deserves Its Own Memory Harness",
    citation_author: ["Pan, Wenbo", "Liu, Shujie", "Zhou, Xiangyang", "Zhang, Shiwei", "Shi, Wanlu", "Xu, Mirror", "Jia, Xiaohua"],
    citation_publication_date: "2026",
    citation_online_date: "2026/04/10",
    citation_conference_title: "Advances in Neural Information Processing Systems (NeurIPS 2026)",
    citation_arxiv_id: "2604.11811",
    citation_pdf_url: "https://arxiv.org/pdf/2604.11811",
    citation_abstract_html_url: "https://arxiv.org/abs/2604.11811",
  },
};

const articleLd = {
  "@context": "https://schema.org",
  "@type": "ScholarlyArticle",
  "@id": "https://mstar.wenbo.io/#article",
  "headline": "M★: Every Task Deserves Its Own Memory Harness",
  "name": "M★: Every Task Deserves Its Own Memory Harness",
  "alternateName": [
    "M*",
    "MStar"
  ],
  "abstract": "Large language model agents rely on specialized memory systems to accumulate and reuse knowledge during extended interactions. Recent architectures typically adopt a fixed memory design tailored to specific domains, such as semantic retrieval for conversations or skills reused for coding. However, a memory system optimized for one purpose frequently fails to transfer to others. To address this limitation, we introduce M★, a method that automatically discovers task-optimized memory harnesses through executable program evolution. Specifically, M★ models an agent memory system as a memory program written in Python. This program encapsulates the data Schema, the storage Logic, and the agent workflow Instructions. We optimize these components jointly using a reflective code evolution method; this approach employs a population-based search strategy and analyzes evaluation failures to iteratively refine the candidate programs. We evaluate M★ on four distinct benchmarks spanning conversation, embodied planning, and expert reasoning. Our results demonstrate that M★ improves performance over existing fixed-memory baselines robustly across all evaluated tasks. Furthermore, the evolved memory programs exhibit structurally distinct processing mechanisms for each domain. This finding indicates that specializing the memory mechanism for a given task explores a broad design space and provides a superior solution compared to general-purpose memory paradigms.",
  "author": [
    {
      "@type": "Person",
      "name": "Wenbo Pan",
      "@id": "https://www.wenbo.io/#person",
      "url": "https://www.wenbo.io/",
      "affiliation": {
        "@type": "CollegeOrUniversity",
        "name": "City University of Hong Kong"
      }
    },
    {
      "@type": "Person",
      "name": "Shujie Liu",
      "affiliation": {
        "@type": "Organization",
        "name": "Microsoft"
      }
    },
    {
      "@type": "Person",
      "name": "Xiangyang Zhou",
      "affiliation": {
        "@type": "Organization",
        "name": "Microsoft"
      }
    },
    {
      "@type": "Person",
      "name": "Shiwei Zhang",
      "affiliation": {
        "@type": "Organization",
        "name": "Microsoft"
      }
    },
    {
      "@type": "Person",
      "name": "Wanlu Shi",
      "affiliation": {
        "@type": "Organization",
        "name": "Microsoft"
      }
    },
    {
      "@type": "Person",
      "name": "Mirror Xu",
      "affiliation": {
        "@type": "Organization",
        "name": "Microsoft"
      }
    },
    {
      "@type": "Person",
      "name": "Xiaohua Jia",
      "affiliation": {
        "@type": "CollegeOrUniversity",
        "name": "City University of Hong Kong"
      }
    }
  ],
  "datePublished": "2026-04-10",
  "publication": {
    "@type": "PublicationEvent",
    "name": "NeurIPS 2026"
  },
  "url": "https://mstar.wenbo.io/",
  "image": "https://mstar.wenbo.io/og.png",
  "sameAs": [
    "https://arxiv.org/abs/2604.11811",
    "https://doi.org/10.48550/arXiv.2604.11811",
    "https://github.com/wbopan/mstar"
  ],
  "keywords": [
    "LLM agents",
    "agent memory",
    "memory harness",
    "program evolution",
    "self-evolving agents"
  ]
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${sans.variable} ${mono.variable} light`}
      style={{ colorScheme: "light" }}
    >
      <body className="min-h-screen bg-background font-sans text-foreground antialiased">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify(articleLd).replace(/</g, "\\u003c"),
          }}
        />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
