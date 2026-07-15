<?php
	$cc = ['#ecd078', '#d95b43', '#c02942', '#542437', '#53777a', '#f5ae33', '#99ac40', '#ff7c7c', '#78c0a8', '#7a6a53', '#6c5b7b', '#c06c84', '#d2ff0f', '#f2c45a', '#3b2d38', '#b8af03', '#d1e751', '#ff3a31', '#99b59a', '#676970', '#ecd078', '#618eff', '#7dffff', '#f07241', '#bcbcbc'];
	
	$cc2 = ['25, 100, 126', '40, 175, 176', '244, 211, 94', '238, 150, 75', '19, 111, 99', '224, 202, 60', '243, 66, 19', '62, 47, 91', '0, 15, 8'];;
	
?>
<html>
<body>
	<div style="width: 400px; display:inline-block; font-size:16px; vertical-align: top;">
	  <?php foreach ($cc as $i=>$c): ?>
		<svg width="200" height="25">
		  <rect width="200" height="25" style="fill:<?php echo $c; ?>;stroke-width:0"/>
		</svg>
		<span><?php echo "palette1 {$i} {$c}"; ?></span>
		<br/>
	  <?php endforeach; ?>
	</div>

	<div style="width: 400px; display:inline-block; font-size:16px; vertical-align: top;">
	  <?php foreach ($cc2 as $i=>$c): ?>
		<svg width="200" height="25">
		  <rect width="200" height="25" style="fill:rgb(<?php echo $c; ?>);stroke-width:0"/>
		</svg>
		<span><?php echo "palette2 {$i} {$c}"; ?></span>
		<br/>
	  <?php endforeach; ?>
	</div>
</body>
</html>