<!DOCTYPE html>
<html lang="{{ str_replace('_', '-', app()->getLocale()) }}">
<head>
	<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">

    <!-- Scripts -->
    <script src="{{ asset('js/app.js') }}"></script>
	<script type="text/javascript" language="javascript" src="https://code.jquery.com/jquery-3.5.1.js"></script>
	<script type="text/javascript" language="javascript" src="https://cdn.datatables.net/1.10.23/js/jquery.dataTables.min.js"></script>
	<script type="text/javascript" src="https://cdn.datatables.net/v/dt/jq-3.3.1/dt-1.10.23/r-2.2.7/sp-1.2.2/sl-1.3.1/datatables.min.js"></script>
	<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js" integrity="sha384-YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz" crossorigin="anonymous"></script>
	<script type="text/javascript" src="/js/script.js?v=2"></script>
	<script type="text/javascript" src="{{ asset('js/db-charts.js') }}?v={{ filemtime(public_path('js/db-charts.js')) }}"></script>

    <!-- Fonts -->
    <link rel="dns-prefetch" href="//fonts.gstatic.com">
    <link rel="preconnect" href="https://fonts.gstatic.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Public+Sans:wght@200;300;400;500;600;700;800&family=Roboto+Mono:wght@400;500&display=swap" rel="stylesheet">

    <!-- Styles -->
	<link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/v/dt/jq-3.3.1/dt-1.10.23/r-2.2.7/sp-1.2.2/sl-1.3.1/datatables.min.css"/>
	<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" integrity="sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH" crossorigin="anonymous">
	
    <title>{{ ($pagetitle ?? null) ? $pagetitle : config('app.name', 'WeGov Research') }}</title>
	@yield('head')
	
    <link href="{{ asset('css/style.css') }}?v={{ filemtime(public_path('css/style.css')) }}" rel="stylesheet">
    <link href="{{ asset('css/loader.css') }}" rel="stylesheet">
    <link href="{{ asset('css/responsive.css') }}" rel="stylesheet">
    <link href="{{ asset('css/app.css') }}" rel="stylesheet">
	<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
	{{-- Databook design system — token + component layer (loads AFTER Bootstrap & style.css so it wins) --}}
	<link href="{{ asset('css/databook-tokens.css') }}?v={{ filemtime(public_path('css/databook-tokens.css')) }}" rel="stylesheet">
	<link href="{{ asset('css/databook-components.css') }}?v={{ filemtime(public_path('css/databook-components.css')) }}" rel="stylesheet">
	<style>
		.bi-tags, .bi-funnel {padding-right: .5rem;}
		.tag-label, .tag-label a {color:#777777; font-weight:600; padding-left:.1em;margin-right:-2px;}
		.tag-label:hover {color:#171717;cursor:pointer;text-decoration:none;}
		.no-underline:hover {text-decoration:none;}
		.tag-label+.tag-label::before {
			padding-right: .2rem;
			color: #6c757d;
			content: ", ";
		}
		.type-label{background: #162E51;border-radius: 4px;color:#fff;padding: 8px 9px;font-weight: normal;font-size: 16px;line-height: 19px;margin-right: 10px;margin-bottom: 10px;}
		[title] {cursor: help;}

	</style>	
	@if ($map ?? null)
		<link href="https://api.mapbox.com/mapbox-gl-js/v2.4.1/mapbox-gl.css" rel="stylesheet">
		<script src="https://api.mapbox.com/mapbox-gl-js/v2.4.1/mapbox-gl.js"></script>
	@endif

	<!-- Global site tag (gtag.js) - Google Analytics -->
	<script async src="https://www.googletagmanager.com/gtag/js?id=G-W87EE6PCQC"></script>
	<script>
	  window.dataLayer = window.dataLayer || [];
	  function gtag(){dataLayer.push(arguments);}
	  gtag('js', new Date());
	  gtag('config', 'G-W87EE6PCQC');
	</script>
	
</head>

<body>
	<!-- Nonprofit Disclaimer Bar -->
	<div id="disclaimer-bar" class="db-disclaimer">
		<span>This website is a nonprofit project of <a href="https://wegov.nyc" target="_blank" rel="noopener">WeGov.NYC</a> and not affiliated with NYC government.</span>
		<button class="db-disclaimer-close" onclick="document.getElementById('disclaimer-bar').style.display='none';sessionStorage.setItem('disclaimerHidden','1');" aria-label="Dismiss">&times;</button>
	</div>
	<script>if(sessionStorage.getItem('disclaimerHidden')){document.getElementById('disclaimer-bar').style.display='none';}</script>
	
	<!-- Loader -->
	<div class="loading" style="display:none;">Loading&#8230;</div>
	<!-- /Loader -->
	
    <div id="app" class="container-fluid p-0">
        <header>
           	@yield('menubar')
        </header>

        <main class="container">
            @yield('content')
        </main>

		<footer class="db-footer">
			<div class="container">
				<div class="db-footer-cols">
					<div>
						<a href="{{ route('root') }}" class="db-brand">DATABOOK.NYC</a>
						<p style="font-size:var(--db-text-sm); color:var(--db-text-on-navy-muted); margin:var(--db-space-1) 0 var(--db-space-2);">Combining dozens of open datasets to help people understand NYC government.</p>
						<h6>Newsletter</h6>
						<div class="db-newsletter">
							<input type="text" id="newsletter-email" placeholder="Your email address" aria-label="Your email address">
							<button class="db-btn db-btn-sm" type="button" style="background:var(--db-accent); color:#fff;" onclick="subscribe_newsletter()">Subscribe</button>
						</div>
					</div>
					<div>
						<h6>Sections</h6>
						<ul>
							<li><a href="//wegov.nyc/news-events/" target="_blank" rel="noopener">News &amp; Events</a></li>
							<li><a href="//wegov.nyc/tools/" target="_blank" rel="noopener">Tools</a></li>
						</ul>
					</div>
					<div>
						<h6>Contribute</h6>
						<ul>
							<li><a href="https://www.notion.so/wegovnyc/Get-Involved-d31cee2e3ea04051b600e0a5b902daab" target="_blank" rel="nofollow">Get Involved</a></li>
							<li><a href="https://opencollective.com/wegovnyc" target="_blank" rel="nofollow">Donate</a></li>
						</ul>
					</div>
					<div>
						<h6>About</h6>
						<ul>
							<li><a href="https://wegov.nyc/about/" target="_blank" rel="noopener">WeGovNYC</a></li>
							<li><a href="http://sarapis.org/about" target="_blank" rel="noopener">Sarapis</a></li>
						</ul>
					</div>
					<div>
						<h6>Social</h6>
						<ul>
							<li><a href="https://twitter.com/wegovnyc" target="_blank" rel="nofollow">Twitter</a></li>
							<li><a href="https://www.facebook.com/wegovnyc" target="_blank" rel="nofollow">Facebook</a></li>
							<li><a href="https://github.com/wegovnyc" target="_blank" rel="nofollow">GitHub</a></li>
						</ul>
					</div>
				</div>

				<div class="db-footer-legal">
					<span><strong style="color:#fff;">WeGovNYC</strong> is a project of <a href="https://sarapis.org/" target="_blank" rel="noopener">Sarapis</a>, a 501.c.3 nonprofit.</span>
					<span style="margin-left:auto; display:inline-flex; gap:8px; align-items:center;">
						<a href="#"><img src="/img/cc.xlarge.png" alt="Creative Commons"></a>
						<a href="#"><img src="/img/by.xlarge.png" alt="Attribution"></a>
						<a href="#"><img src="/img/sa.xlarge.png" alt="ShareAlike"></a>
					</span>
				</div>
			</div>
		</footer>

		<div id="return-to-top" style="display:none;">
			<a href="#" onclick="topFunction()"><span>Return to top</span> <i class="bi bi-arrow-up-circle-fill"></i></a>
		</div>
		@yield('scripts')

		{{-- Chat Widget (hidden — re-enable when ready) --}}
		{{-- @include('sub.chat_widget') --}}
    </div>

	{{-- Global shell behavior: responsive nav drawer toggle (ported from db-shell.js) --}}
	<script>
	(function(){
		var t=document.getElementById('dbNavToggle'), n=document.getElementById('dbNav');
		if(t&&n){t.addEventListener('click',function(){
			var open=n.classList.toggle('is-open');
			t.setAttribute('aria-expanded',open?'true':'false');
			var i=t.querySelector('.bi'); if(i){ i.className=open?'bi bi-x-lg':'bi bi-list'; }
		});}
	})();
	</script>

	{{-- Dropdown category tabs (.db-tab-dd) — profile section navs (org/title/district).
	     Links inside are real <a href> sub-routes; this is progressive enhancement only.
	     One menu open at a time; click-outside + Esc close; arrow keys navigate. --}}
	<script>
	(function(){
		var dds = Array.prototype.slice.call(document.querySelectorAll('.db-tab-dd'));
		if(!dds.length) return;
		function items(dd){ return Array.prototype.slice.call(dd.querySelectorAll('.db-tab-menu [role="menuitem"]')); }
		function close(dd){
			dd.classList.remove('is-open');
			var b=dd.querySelector('[data-dd]'); if(b) b.setAttribute('aria-expanded','false');
		}
		function closeAll(except){ dds.forEach(function(d){ if(d!==except) close(d); }); }
		function open(dd){
			closeAll(dd);
			dd.classList.add('is-open');
			var b=dd.querySelector('[data-dd]'); if(b) b.setAttribute('aria-expanded','true');
		}
		dds.forEach(function(dd){
			var btn=dd.querySelector('[data-dd]');
			if(!btn) return;
			btn.addEventListener('click', function(e){
				e.preventDefault();
				if(dd.classList.contains('is-open')){ close(dd); } else { open(dd); }
			});
			btn.addEventListener('keydown', function(e){
				if(e.key==='Enter'||e.key===' '||e.key==='ArrowDown'){
					e.preventDefault(); open(dd);
					var it=items(dd); if(it[0]) it[0].focus();
				} else if(e.key==='Escape'){ close(dd); }
			});
			items(dd).forEach(function(item, i, arr){
				item.addEventListener('keydown', function(e){
					if(e.key==='ArrowDown'){ e.preventDefault(); (arr[i+1]||arr[0]).focus(); }
					else if(e.key==='ArrowUp'){ e.preventDefault(); (arr[i-1]||arr[arr.length-1]).focus(); }
					else if(e.key==='Escape'){ e.preventDefault(); close(dd); btn.focus(); }
				});
			});
		});
		document.addEventListener('click', function(e){
			if(!e.target.closest || !e.target.closest('.db-tab-dd')) closeAll(null);
		});
		document.addEventListener('keydown', function(e){ if(e.key==='Escape') closeAll(null); });
	})();
	</script>

</body>
</html>

