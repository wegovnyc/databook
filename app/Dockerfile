FROM php:7.4-fpm

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    libpng-dev \
    libonig-dev \
    libxml2-dev \
    zip \
    unzip

# Clear cache
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# Install PHP extensions (including OPcache for production performance)
RUN docker-php-ext-install pdo_mysql mbstring exif pcntl bcmath gd opcache

# OPcache production config — ~13x faster page loads
RUN echo "opcache.enable=1\n\
opcache.memory_consumption=128\n\
opcache.interned_strings_buffer=16\n\
opcache.max_accelerated_files=10000\n\
opcache.revalidate_freq=60\n\
opcache.fast_shutdown=1\n\
opcache.enable_cli=0\n\
opcache.save_comments=1" > /usr/local/etc/php/conf.d/opcache-recommended.ini

# PHP-FPM worker tuning for traffic (3.7GB RAM server, ~30MB per worker)
RUN sed -i 's/pm.max_children = 5/pm.max_children = 15/' /usr/local/etc/php-fpm.d/www.conf && \
    sed -i 's/pm.start_servers = 2/pm.start_servers = 5/' /usr/local/etc/php-fpm.d/www.conf && \
    sed -i 's/pm.min_spare_servers = 1/pm.min_spare_servers = 3/' /usr/local/etc/php-fpm.d/www.conf && \
    sed -i 's/pm.max_spare_servers = 3/pm.max_spare_servers = 8/' /usr/local/etc/php-fpm.d/www.conf

# Get latest Composer
COPY --from=composer:latest /usr/bin/composer /usr/bin/composer

# Set working directory
WORKDIR /var/www

# Copy existing application directory contents
COPY . /var/www

# Remove composer.lock to allow fresh resolution for PHP 7.4
RUN rm -f composer.lock

# Install dependencies
RUN composer install --no-interaction --optimize-autoloader --no-dev

# Pre-compile Blade templates and cache config for production
RUN php artisan view:cache || true
RUN php artisan config:cache || true

# Change current user to www
RUN chown -R www-data:www-data /var/www

# Expose port 9000 and start php-fpm server
EXPOSE 9000
CMD ["php-fpm"]
