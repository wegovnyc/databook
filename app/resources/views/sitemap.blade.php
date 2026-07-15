{!! '<' . '?xml version="1.0" encoding="UTF-8"?' . '>' !!}
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  @foreach ($entries as $entry)
	<url><loc>{!! $entry[0] !!}</loc><lastmod>{!! date('Y-m-d') !!}</lastmod><priority>{!! sprintf('%.2f', $entry[1]) !!}</priority><changefreq>{!! $entry[2] !!}</changefreq></url>
  @endforeach
</urlset>
